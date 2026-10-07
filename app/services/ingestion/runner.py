import asyncio
import sys
from app.core.log import logger
from app.services.ingestion.pipeline import execute_daily_ingestion_pipeline


async def main() -> None:
    from app.core.log import setup_logging
    setup_logging()
    logger.info("Triggering Phase 1 News Ingestion & Scoring via CLI...")
    try:
        result = await execute_daily_ingestion_pipeline()
        print("\n" + "=" * 60)
        print("NEWS INGESTION & SCORING PIPELINE SUMMARY")
        print("=" * 60)
        print(f"Sources Checked     : {result.sources_checked}")
        print(f"Articles Ingested   : {result.articles_ingested}")
        print(f"Candidates Screened : {result.candidates_screened}")
        print(f"Candidates Verified : {result.candidates_verified}")
        print(f"Winning Article ID  : {result.winning_article_id}")
        print(f"Winning Title       : {result.winning_article_title}")
        print(f"Winning Score       : {result.winning_composite_score}")
        print("=" * 60 + "\n")
    except Exception as e:
        logger.error(f"Ingestion pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
