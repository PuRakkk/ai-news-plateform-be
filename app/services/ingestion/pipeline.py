import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlmodel import Session
from app.core.config import settings
from app.core.database import get_session
from app.core.log import logger
from app.models.news import Article, ArticleScore, ArticleVerification, NewsSource
from app.repositories.news_repo import (
    ArticleRepository,
    ArticleScoreRepository,
    ArticleVerificationRepository,
    NewsSourceRepository,
)
from app.schemas.news import IngestionSummaryDTO
from app.services.ingestion.rss_fetcher import fetch_rss_feed, is_published_today
from app.services.ingestion.scorer import score_article_utility
from app.services.ingestion.text_extractor import extract_article_text
from app.services.ingestion.verifier import (
    cluster_candidates,
    find_secondary_candidate,
    search_external_secondary_source,
    verify_article_corroboration,
)
from app.services.llm.base import LLMProviderAdapter
from app.services.llm.factory import get_llm_provider


class IngestionPipeline:
    """Orchestrates the 4-stage news ingestion, verification, and scoring pipeline."""

    def __init__(self, session: Session, llm_provider: LLMProviderAdapter | None = None) -> None:
        self.session = session
        self.source_repo = NewsSourceRepository(session)
        self.article_repo = ArticleRepository(session)
        self.verification_repo = ArticleVerificationRepository(session)
        self.score_repo = ArticleScoreRepository(session)
        self.llm_provider = llm_provider or get_llm_provider()

    async def run(self, client_id: uuid.UUID | None = None) -> IngestionSummaryDTO:
        logger.info("=" * 70)
        logger.info(">>> STARTING NEWS INGESTION & VERIFICATION PIPELINE")
        logger.info("=" * 70)

        # 0. Resolve target clients and topic filter mandates
        from app.repositories.client_repo import ClientProfileRepository
        client_repo = ClientProfileRepository(self.session)
        target_clients: list[tuple[Any, Any]] = []
        if client_id:
            cl, _, tf = client_repo.get_client_bundle(client_id)
            if cl:
                target_clients.append((cl, tf))
        else:
            active_clients = list(client_repo.get_active_clients())
            for cl in active_clients:
                _, _, tf = client_repo.get_client_bundle(cl.id)
                target_clients.append((cl, tf))

        def build_client_topic_filter_dict(tf: Any) -> dict[str, Any] | None:
            if not tf:
                return None
            return {
                "industries": tf.industries,
                "focus_keywords": tf.focus_keywords,
                "excluded_keywords": tf.excluded_keywords,
                "weights": {
                    "actionability": tf.weight_actionability,
                    "economic_impact": tf.weight_economic,
                    "regulatory_impact": tf.weight_regulatory,
                    "novelty": tf.weight_novelty,
                },
            }

        def extract_keywords_from_filter(tf: Any) -> list[str]:
            if not tf:
                return []
            raw_kw = f"{tf.focus_keywords} {tf.industries}".lower()
            tokens: list[str] = []
            for token in raw_kw.replace(",", " ").split():
                clean_t = token.strip(" \"'[],")
                if len(clean_t) > 2:
                    tokens.append(clean_t)
            return tokens

        if target_clients:
            logger.info(f"Loaded {len(target_clients)} active client mandate(s):")
            for cl, tf in target_clients:
                inds = tf.industries if tf else "[]"
                kws = tf.focus_keywords if tf else "[]"
                logger.info(f"  - Client '{cl.name}': Industries={inds}, Keywords={kws}")
        else:
            logger.info("No custom clients configured. Proceeding with default general executive mandate.")

        # Ensure default authority sources exist
        self.source_repo.seed_default_sources()
        sources = self.source_repo.get_active_sources()
        sources_checked = len(sources)

        # ------------------------------------------------------------------
        # STAGE 1: CONCURRENT HYBRID INGESTION
        # ------------------------------------------------------------------
        logger.info(f"\n[STAGE 1/4: CONCURRENT INGESTION] Polling {sources_checked} active authority sources...")
        sem = asyncio.Semaphore(5)

        async def fetch_source_task(src: NewsSource) -> tuple[NewsSource, list[dict[str, Any]]]:
            async with sem:
                try:
                    items = await fetch_rss_feed(src.feed_url)
                    return src, items
                except Exception as exc:
                    logger.warning(f"Error fetching feed '{src.name}': {exc}")
                    return src, []

        fetched_results = await asyncio.gather(*(fetch_source_task(s) for s in sources))

        ingested_count = 0
        raw_candidates: list[dict[str, Any]] = []

        for source, items in fetched_results:
            src_new = 0
            src_existing = 0

            for item in items:
                article_obj = Article(
                    source_id=source.id,
                    client_id=client_id,
                    url=item["url"],
                    title=item["title"],
                    summary=item.get("summary"),
                    full_text=item.get("summary") or item["title"],
                    content_hash=item["content_hash"],
                    published_at=item.get("published_at"),
                    status="pending",
                )
                saved_article, created = self.article_repo.create_if_not_exists(article_obj)
                if created:
                    ingested_count += 1
                    src_new += 1
                else:
                    src_existing += 1

                raw_candidates.append(
                    {
                        "id": str(saved_article.id),
                        "url": saved_article.url,
                        "title": saved_article.title,
                        "summary": saved_article.summary,
                        "published_at": saved_article.published_at,
                    }
                )

            logger.info(f"  [Feed Complete] {source.name}: {len(items)} items ({src_new} new, {src_existing} deduplicated)")

        logger.info(
            f"--> [STAGE 1 COMPLETE] Ingested {ingested_count} new articles into news lake. "
            f"Total raw items processed: {len(raw_candidates)}."
        )

        if not raw_candidates:
            # Fall back to recent articles from DB if feeds had no items
            logger.info("  No items from feeds; loading recent articles from database lake...")
            recent = self.article_repo.get_recent_articles(limit=30)
            raw_candidates = [
                {
                    "id": str(a.id),
                    "url": a.url,
                    "title": a.title,
                    "summary": a.summary,
                    "published_at": a.published_at,
                }
                for a in recent
            ]

        if not raw_candidates:
            logger.warning("--> No candidates available in database. Ingestion pipeline aborted.")
            return IngestionSummaryDTO(
                sources_checked=sources_checked,
                articles_ingested=ingested_count,
                candidates_screened=0,
                candidates_verified=0,
            )

        # Sort all raw candidates reverse-chronologically (newest breaking news first)
        raw_candidates.sort(
            key=lambda c: c.get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

        # Cluster stories covering the same breaking event into unified leads
        clustered_candidates = cluster_candidates(raw_candidates)
        logger.info(
            f"--> Clustered {len(raw_candidates)} raw candidate articles into "
            f"{len(clustered_candidates)} distinct story clusters."
        )

        # Prioritize clusters matching client editorial mandates (keywords / industries)
        if target_clients:
            for c in clustered_candidates:
                title_lower = (c.get("title") or "").lower()
                summary_lower = (c.get("summary") or "").lower()
                max_affinity = 0.0

                for cl, tf in target_clients:
                    tf_dict = build_client_topic_filter_dict(tf)
                    if not tf_dict:
                        continue
                    cl_kw_list = extract_keywords_from_filter(tf)
                    raw_focus = (tf_dict.get("focus_keywords") or "").replace('"', "").replace("[", "").replace("]", "")
                    raw_ind = (tf_dict.get("industries") or "").replace('"', "").replace("[", "").replace("]", "")
                    raw_ex = (tf_dict.get("excluded_keywords") or "").replace('"', "").replace("[", "").replace("]", "")

                    focus_phrases = [kw.strip().lower() for kw in raw_focus.split(",") if kw.strip()] + [
                        ind.strip().lower() for ind in raw_ind.split(",") if ind.strip()
                    ]
                    excluded_phrases = [ex.strip().lower() for ex in raw_ex.split(",") if ex.strip()]

                    cl_aff = 0.0
                    if any(ex in title_lower or ex in summary_lower for ex in excluded_phrases):
                        cl_aff -= 50.0

                    for phrase in focus_phrases:
                        if phrase in title_lower:
                            cl_aff += 5.0
                        elif phrase in summary_lower:
                            cl_aff += 2.0

                    for token in cl_kw_list:
                        if token in title_lower:
                            cl_aff += 2.0
                        elif token in summary_lower:
                            cl_aff += 1.0

                    if cl_aff > max_affinity:
                        max_affinity = cl_aff

                c["_client_affinity"] = max_affinity

            # Sort by client affinity descending, then publication date descending
            clustered_candidates.sort(
                key=lambda c: (
                    c.get("_client_affinity", 0.0),
                    c.get("published_at") or datetime.min.replace(tzinfo=timezone.utc),
                ),
                reverse=True,
            )
            matched_count = sum(1 for c in clustered_candidates if c.get("_client_affinity", 0.0) > 0)
            logger.info(
                f"--> Client mandates applied: {matched_count}/{len(clustered_candidates)} story clusters "
                f"match client focus keywords/industries."
            )

        # ------------------------------------------------------------------
        # STAGE 2: FAST SCREENING FILTER
        # ------------------------------------------------------------------
        logger.info(f"\n[STAGE 2/4: FAST SCREENING FILTER] Evaluating candidate stories against client mandate(s)...")
        # Evaluate up to 60 cluster leads across the entire candidate pool
        screening_payload = [
            {
                "id": c["id"],
                "title": c["title"],
                "url": c.get("url", ""),
                "summary": (c.get("summary") or "")[:200],
            }
            for c in clustered_candidates[:60]
        ]
        top_k_screen = getattr(settings, "INGESTION_TOP_K", 10)
        logger.info(f"  Submitting {len(screening_payload)} candidate summaries for batch evaluation (top_k={top_k_screen})...")

        # Build screening topic filter
        screening_topic_filter: dict[str, Any] | None = None
        if len(target_clients) == 1 and target_clients[0][1]:
            screening_topic_filter = build_client_topic_filter_dict(target_clients[0][1])
        elif len(target_clients) > 1:
            all_inds = []
            all_focs = []
            for _, tf in target_clients:
                if tf:
                    if tf.industries:
                        all_inds.append(tf.industries)
                    if tf.focus_keywords:
                        all_focs.append(tf.focus_keywords)
            if all_inds or all_focs:
                screening_topic_filter = {
                    "industries": ", ".join(all_inds),
                    "focus_keywords": ", ".join(all_focs),
                }

        try:
            screened_results = await self.llm_provider.screen_candidates(
                screening_payload, top_k=top_k_screen, topic_filter=screening_topic_filter
            )
        except TypeError:
            screened_results = await self.llm_provider.screen_candidates(
                screening_payload, top_k=top_k_screen
            )
        candidates_screened = len(screened_results)

        candidate_map = {c["id"]: c for c in clustered_candidates}
        shortlist: list[dict[str, Any]] = []

        logger.info(f"--> [STAGE 2 SCREENING RESULTS] Shortlisted {candidates_screened} candidate stories:")
        for rank, s in enumerate(screened_results, start=1):
            art_id_str = s.get("article_id")
            if art_id_str and art_id_str in candidate_map:
                art_data = candidate_map[art_id_str]
                art_data["screening_reason"] = s.get("screening_reason")
                art_data["relevance_score"] = s.get("relevance_score", 0.5)
                shortlist.append(art_data)
                self.article_repo.update_status(uuid.UUID(art_id_str), "screened")
                logger.info(
                    f"  [#{rank}] (Score: {art_data['relevance_score']}) {art_data['title'][:65]}...\n"
                    f"       Reason: {art_data.get('screening_reason')}"
                )

        logger.info(f"--> [STAGE 2 COMPLETE] Shortlist created with {len(shortlist)} stories.")

        # ------------------------------------------------------------------
        # STAGE 3: DEEP DUAL-SOURCE VERIFICATION
        # ------------------------------------------------------------------
        logger.info(f"\n[STAGE 3/4: DUAL-SOURCE VERIFICATION] Cross-checking factual consistency...")
        verified_candidates: list[dict[str, Any]] = []

        for idx, cand in enumerate(shortlist, start=1):
            cand_id = uuid.UUID(cand["id"])
            logger.info(f"\n  [Candidate {idx}/{len(shortlist)}] \"{cand['title']}\"")
            logger.info(f"    Primary URL: {cand['url']}")

            primary_text = await extract_article_text(cand["url"])
            if primary_text:
                logger.info(f"    Extracted primary text: {len(primary_text)} characters")
            else:
                primary_text = cand.get("summary") or cand["title"]
                logger.info("    Primary text extraction blocked/fallback: using RSS summary")

            # Always persist full_text for candidate article
            self.article_repo.update_full_text(cand_id, primary_text)

            # 1. Search pool or cluster for independent secondary source
            secondary_cand = find_secondary_candidate(cand, raw_candidates)
            secondary_text = ""

            # 2. Active Web Search Fallback if no independent secondary in batch pool
            if not secondary_cand:
                logger.info("    No local batch corroboration found. Triggering active search fallback...")
                secondary_cand = await search_external_secondary_source(cand["title"], cand["url"])

            if secondary_cand:
                src_label = secondary_cand.get("source_name") or secondary_cand.get("url")
                logger.info(f"    Found corroborating candidate ({src_label}): {secondary_cand['url']}")
                secondary_text = await extract_article_text(secondary_cand["url"])
                if not secondary_text:
                    secondary_text = secondary_cand.get("summary") or secondary_cand["title"]
                if secondary_cand.get("id"):
                    self.article_repo.update_full_text(uuid.UUID(secondary_cand["id"]), secondary_text)
            else:
                logger.info("    No independent root-domain article found (local batch or external search).")

            verif_result = await verify_article_corroboration(
                primary_article=cand,
                secondary_article=secondary_cand,
                primary_text=primary_text,
                secondary_text=secondary_text,
                llm_provider=self.llm_provider,
            )

            # Persist verification in database
            verif_record = ArticleVerification(
                article_id=cand_id,
                secondary_url=verif_result.get("secondary_url"),
                secondary_source=verif_result.get("secondary_source"),
                agreement_score=float(verif_result.get("agreement_score", 0.0)),
                corroboration_notes=verif_result.get("corroboration_notes"),
                is_verified=bool(verif_result.get("is_verified", False)),
            )
            self.verification_repo.upsert_verification(verif_record)

            cand["primary_text"] = primary_text
            cand["is_verified"] = verif_record.is_verified
            cand["agreement_score"] = verif_record.agreement_score

            status_label = "VERIFIED (>= 0.75)" if verif_record.is_verified else "UNVERIFIED (< 0.75)"
            logger.info(
                f"    -> Result: {status_label} (Agreement Score: {verif_record.agreement_score:.2f})\n"
                f"       Audit Notes: {verif_record.corroboration_notes}"
            )

            if verif_record.is_verified:
                self.article_repo.update_status(cand_id, "verified")
                verified_candidates.append(cand)
            else:
                self.article_repo.update_status(cand_id, "unverified")

        candidates_verified = len(verified_candidates)
        logger.info(f"\n--> [STAGE 3 COMPLETE] {candidates_verified}/{len(shortlist)} candidates verified by dual sources.")

        # Cascading fallback: if none passed >= 0.75, fall back to shortlisted candidates
        scoring_pool = verified_candidates if verified_candidates else shortlist
        if not verified_candidates and shortlist:
            logger.warning("--> Cascading Fallback: No candidate met 0.75 agreement. Evaluating top shortlisted stories.")

        # ------------------------------------------------------------------
        # STAGE 4: BUSINESS UTILITY SCORING & SELECTION (PER-CLIENT DYNAMIC)
        # ------------------------------------------------------------------
        logger.info(f"\n[STAGE 4/4: BUSINESS UTILITY SCORING] Evaluating executive impact & electing winner(s)...")

        client_winners: dict[str, uuid.UUID] = {}
        overall_best_candidate: dict[str, Any] | None = None
        overall_best_score_record: ArticleScore | None = None
        overall_highest_composite = -1.0

        clients_to_evaluate: list[tuple[Any | None, Any | None]] = (
            [(cl, tf) for cl, tf in target_clients]
            if target_clients
            else [(None, None)]
        )

        for cl, tf in clients_to_evaluate:
            cl_id = cl.id if cl else None
            cl_name = cl.name if cl else "Default Baseline Profile"
            cl_criteria = build_client_topic_filter_dict(tf)
            logger.info(f"\n--> [CLIENT EVALUATION] Scoring candidates for: '{cl_name}' (id={cl_id})...")

            best_candidate_for_cl: dict[str, Any] | None = None
            best_score_record_for_cl: ArticleScore | None = None
            highest_composite_for_cl = -1.0

            for idx, cand in enumerate(scoring_pool, start=1):
                cand_id = uuid.UUID(cand["id"])
                full_text = cand.get("primary_text") or cand.get("summary") or cand["title"]
                scores = await score_article_utility(
                    title=cand["title"],
                    full_text=full_text,
                    llm_provider=self.llm_provider,
                    client_criteria=cl_criteria,
                )

                raw_composite = float(scores.get("composite_score", 0.0))
                cand_pub_dt = cand.get("published_at")
                is_today = is_published_today(cand_pub_dt)
                freshness_bonus = settings.RSS_TODAY_FRESHNESS_BONUS if is_today else 0.0
                final_composite = min(1.0, round(raw_composite + freshness_bonus, 2))

                # Penalty if candidate contains excluded keywords for this client
                if tf and tf.excluded_keywords:
                    raw_ex = (tf.excluded_keywords or "").lower().replace('"', "").replace("[", "").replace("]", "")
                    ex_list = [k.strip() for k in raw_ex.split(",") if k.strip()]
                    cand_text_lower = f"{cand['title']} {full_text}".lower()
                    if any(ex in cand_text_lower for ex in ex_list):
                        final_composite = max(0.0, round(final_composite - 0.40, 2))
                        logger.info(f"    [Client {cl_name}] Applied penalty for excluded keyword match in '{cand['title'][:40]}'")

                reasoning_prefix = f"[Freshness +{freshness_bonus:.2f}] " if freshness_bonus > 0 else ""
                final_reasoning = f"{reasoning_prefix}{scores.get('reasoning') or ''}".strip()

                score_record = ArticleScore(
                    article_id=cand_id,
                    client_id=cl_id,
                    composite_score=final_composite,
                    actionability=float(scores.get("actionability", 0.0)),
                    economic_impact=float(scores.get("economic_impact", 0.0)),
                    regulatory_impact=float(scores.get("regulatory_impact", 0.0)),
                    novelty=float(scores.get("novelty", 0.0)),
                    reasoning=final_reasoning,
                    is_selected=False,
                )
                self.score_repo.upsert_score(score_record)

                bonus_label = f" (+{freshness_bonus:.2f} today)" if freshness_bonus > 0 else ""
                logger.info(
                    f"  [{cl_name}][{idx}/{len(scoring_pool)}] \"{cand['title'][:48]}...\"\n"
                    f"       Score: {score_record.composite_score:.2f}{bonus_label} "
                    f"(Act: {score_record.actionability:.2f}, Econ: {score_record.economic_impact:.2f}, "
                    f"Reg: {score_record.regulatory_impact:.2f}, Nov: {score_record.novelty:.2f})"
                )

                cand_dt = cand_pub_dt or datetime.min.replace(tzinfo=timezone.utc)
                best_dt = (
                    best_candidate_for_cl.get("published_at") or datetime.min.replace(tzinfo=timezone.utc)
                    if best_candidate_for_cl
                    else datetime.min.replace(tzinfo=timezone.utc)
                )

                is_better = False
                if score_record.composite_score > highest_composite_for_cl:
                    is_better = True
                elif abs(score_record.composite_score - highest_composite_for_cl) <= 0.01:
                    # Tie-breaker: newer publication timestamp wins
                    if cand_dt > best_dt:
                        is_better = True

                if is_better:
                    highest_composite_for_cl = score_record.composite_score
                    best_candidate_for_cl = cand
                    best_score_record_for_cl = score_record

            if best_candidate_for_cl and best_score_record_for_cl:
                cl_winning_id = uuid.UUID(best_candidate_for_cl["id"])
                self.score_repo.set_winning_article(cl_winning_id, cl_id)
                self.article_repo.update_status(cl_winning_id, "selected")
                if cl_id:
                    client_winners[str(cl_id)] = cl_winning_id

                logger.info(
                    f"\n>>> [ELECTED WINNER FOR '{cl_name}']:\n"
                    f"    Title           : {best_candidate_for_cl['title']}\n"
                    f"    URL             : {best_candidate_for_cl['url']}\n"
                    f"    Composite Score : {best_score_record_for_cl.composite_score:.2f}\n"
                    f"    Article ID      : {cl_winning_id}\n"
                )

                if best_score_record_for_cl.composite_score > overall_highest_composite:
                    overall_highest_composite = best_score_record_for_cl.composite_score
                    overall_best_candidate = best_candidate_for_cl
                    overall_best_score_record = best_score_record_for_cl

        # Ensure default baseline winner is set if multiple clients ran
        if target_clients and len(target_clients) > 0 and overall_best_candidate and overall_best_score_record:
            overall_id = uuid.UUID(overall_best_candidate["id"])
            default_score = self.score_repo.get_by_article_id(overall_id, client_id=None)
            if not default_score:
                default_score = ArticleScore(
                    article_id=overall_id,
                    client_id=None,
                    composite_score=overall_best_score_record.composite_score,
                    actionability=overall_best_score_record.actionability,
                    economic_impact=overall_best_score_record.economic_impact,
                    regulatory_impact=overall_best_score_record.regulatory_impact,
                    novelty=overall_best_score_record.novelty,
                    reasoning=overall_best_score_record.reasoning,
                    is_selected=True,
                )
                self.score_repo.upsert_score(default_score)
            else:
                self.score_repo.set_winning_article(overall_id, client_id=None)

        winning_id = uuid.UUID(overall_best_candidate["id"]) if overall_best_candidate else None
        winning_title = overall_best_candidate["title"] if overall_best_candidate else None
        winning_score = overall_best_score_record.composite_score if overall_best_score_record else 0.0

        return IngestionSummaryDTO(
            sources_checked=sources_checked,
            articles_ingested=ingested_count,
            candidates_screened=candidates_screened,
            candidates_verified=candidates_verified,
            winning_article_id=winning_id,
            winning_article_title=winning_title,
            winning_composite_score=winning_score,
            client_winners=client_winners,
        )


async def execute_daily_ingestion_pipeline(client_id: uuid.UUID | None = None) -> IngestionSummaryDTO:
    """Async entrypoint for cron scheduling or manual triggering."""
    with get_session() as session:
        pipeline = IngestionPipeline(session)
        return await pipeline.run(client_id=client_id)
