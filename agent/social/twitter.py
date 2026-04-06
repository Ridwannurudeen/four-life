"""Twitter/X integration for posting and monitoring."""

import tweepy
from loguru import logger

from agent.config import settings


class TwitterClient:
    """Handles posting to Twitter/X."""

    def __init__(self) -> None:
        self.enabled = bool(
            settings.twitter_consumer_key and settings.twitter_access_token
        )
        self._client: tweepy.Client | None = None
        self._api: tweepy.API | None = None

        if self.enabled:
            self._client = tweepy.Client(
                bearer_token=settings.twitter_bearer_token,
                consumer_key=settings.twitter_consumer_key,
                consumer_secret=settings.twitter_consumer_secret,
                access_token=settings.twitter_access_token,
                access_token_secret=settings.twitter_access_token_secret,
                wait_on_rate_limit=True,
            )
            # V1.1 API for media uploads
            auth = tweepy.OAuthHandler(
                settings.twitter_consumer_key,
                settings.twitter_consumer_secret,
            )
            auth.set_access_token(
                settings.twitter_access_token,
                settings.twitter_access_token_secret,
            )
            self._api = tweepy.API(auth)
            logger.info("Twitter client initialized")
        else:
            logger.warning("Twitter not configured — posts will be logged only")

    def post_tweet(self, text: str, reply_to: str | None = None) -> str | None:
        """Post a tweet. Returns tweet ID or None if not configured."""
        if not self.enabled:
            logger.info("[DRY RUN] Tweet: {}", text)
            return None

        kwargs = {"text": text}
        if reply_to:
            kwargs["in_reply_to_tweet_id"] = reply_to

        response = self._client.create_tweet(**kwargs)
        tweet_id = response.data["id"]
        logger.info("Posted tweet {}: {}", tweet_id, text[:80])
        return tweet_id

    def post_thread(self, tweets: list[str]) -> list[str]:
        """Post a thread of tweets. Returns list of tweet IDs."""
        ids = []
        reply_to = None
        for tweet in tweets:
            tweet_id = self.post_tweet(tweet, reply_to=reply_to)
            if tweet_id:
                ids.append(tweet_id)
                reply_to = tweet_id
        logger.info("Posted thread: {} tweets", len(ids))
        return ids

    def post_with_image(
        self, text: str, image_bytes: bytes, filename: str = "meme.png"
    ) -> str | None:
        """Post a tweet with an image attachment."""
        if not self.enabled:
            logger.info("[DRY RUN] Tweet with image: {}", text[:80])
            return None

        import tempfile
        import os

        # Save image temporarily for upload
        tmp_path = os.path.join(tempfile.gettempdir(), filename)
        with open(tmp_path, "wb") as f:
            f.write(image_bytes)

        try:
            media = self._api.media_upload(tmp_path)
            response = self._client.create_tweet(
                text=text, media_ids=[media.media_id]
            )
            tweet_id = response.data["id"]
            logger.info("Posted tweet with image {}: {}", tweet_id, text[:80])
            return tweet_id
        finally:
            os.unlink(tmp_path)
