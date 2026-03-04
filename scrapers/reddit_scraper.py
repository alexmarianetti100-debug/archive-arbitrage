import asyncio
import re
from typing import List, Dict, Optional
from datetime import datetime, timedelta

class RedditScraper:
    """Monitor Reddit for snipe bot insights and token discussions."""
    
    def __init__(self):
        self.subreddits = ['solana', 'crypto', 'solana_memes']
        self.keywords = [
            'snipe', 'sniping', 'sniper', 'sniped', 'snipebot',
            'pump.fun', 'pump', 'launch', 'new token', 'meme coin',
            'token snipe', 'snipe trade', 'snipe alert'
        ]
        self.last_checked = None
        self.processed_posts = set()
        
    async def monitor(self):
        """Main monitoring loop."""
        print("🔍 Starting Reddit monitoring for snipe insights...")
        
        # Initial scan
        await self.scan_posts()
        
        # Continue monitoring
        while True:
            await asyncio.sleep(60)  # Check every minute
            await self.scan_posts()
    
    async def scan_posts(self):
        """Scan Reddit for relevant posts."""
        print("📅 Scanning Reddit for new posts...")
        
        # Simulate fetching Reddit posts (replace with actual API calls)
        posts = self._fetch_simulated_posts()
        
        for post in posts:
            await self.process_post(post)
    
    def _fetch_simulated_posts(self) -> List[Dict]:
        """Simulate fetching posts from Reddit."""
        return [
            {
                'title': 'Just sniped a new $MEME token on pump.fun!',
                'author': 'crypto_trader_123',
                'score': 234,
                'url': 'https://reddit.com/r/solana/comments/12345/just_sniped_new_meme_token',
                'created_utc': datetime.now() - timedelta(minutes=15),
                'selftext': 'I managed to snipe this new token before the hype hit. The absorption was 98% and it pumped 50x in 5 minutes! Anyone else get in?'
            },
            {
                'title': 'Are snipe bots still profitable in 2024?',
                'author': 'solana_newbie',
                'score': 156,
                'url': 'https://reddit.com/r/solana/comments/67890/are_snipe_bots_still_profitable',
                'created_utc': datetime.now() - timedelta(minutes=45),
                'selftext': 'I see a lot of posts about snipe bots but wondering if they still work with all the competition these days...'
            },
            {
                'title': 'New token $ALPHA just launched on pump.fun - snipe bots detected!',
                'author': 'whale_watcher',
                'score': 412,
                'url': 'https://reddit.com/r/solana/comments/abc123/new_token_alpha_launched',
                'created_utc': datetime.now() - timedelta(minutes=5),
                'selftext': 'The token just launched and I can see multiple snipe bots already in the liquidity. This might be a good one to watch!'
            },
            {
                'title': 'My pump.fun snipe bot strategy 2024 edition',
                'author': 'trading_pro',
                'score': 567,
                'url': 'https://reddit.com/r/solana/comments/def456/my_pumpfun_snipe_bot_strategy',
                'created_utc': datetime.now() - timedelta(hours=2),
                'selftext': 'Here\'s my updated strategy for sniping tokens on pump.fun. Key points: 1) Watch for high volume launches 2) Use RPC endpoints 3) Set gas bribes correctly...'
            }
        ]
    
    async def process_post(self, post: Dict):
        """Process individual Reddit post."""
        post_url = post['url']
        
        if post_url in self.processed_posts:
            return
            
        print(f"📡 Processing post: {post['title']}")
        
        # Check if post contains relevant keywords
        if self._is_relevant_post(post):
            print(f"🔥 RELEVANT POST FOUND: {post['title']}")
            await self.analyze_post(post)
        
        # Add to processed posts
        self.processed_posts.add(post_url)
    
    def _is_relevant_post(self, post: Dict) -> bool:
        """Check if post is relevant to sniping."""
        # Combine title and selftext for analysis
        text = f"{post['title']} {post.get('selftext', '')}"
        text_lower = text.lower()
        
        # Check for keywords
        for keyword in self.keywords:
            if keyword in text_lower:
                return True
        
        return False
    
    async def analyze_post(self, post: Dict):
        """Analyze relevant post for snipe insights."""
        print(f"🔍 Analyzing post for snipe insights...")
        
        # Extract token symbols
        tokens = self._extract_token_symbols(post)
        
        if tokens:
            print(f"🪙 Tokens found: {', '.join(tokens)}")
        
        # Analyze sentiment
        sentiment = self._analyze_sentiment(post)
        print(f"😊 Sentiment: {sentiment}")
        
        # Extract strategy insights
        insights = self._extract_insights(post)
        if insights:
            print(f"💡 Strategy insights:")
            for insight in insights:
                print(f"   - {insight}")
        
        # Check for urgent opportunities
        if self._is_urgent_opportunity(post):
            print(f"🚨 URGENT OPPORTUNITY: {post['title']}")
            # TODO: Trigger snipe bot
            await self.trigger_snipe_insights(post)
    
    def _extract_token_symbols(self, post: Dict) -> List[str]:
        """Extract token symbols from post."""
        text = f"{post['title']} {post.get('selftext', '')}"
        
        # Look for $TOKEN patterns
        matches = re.findall(r'\$([A-Z0-9]{3,10})', text)
        return list(set(matches))  # Remove duplicates
    
    def _analyze_sentiment(self, post: Dict) -> str:
        """Analyze sentiment of post."""
        text = f"{post['title']} {post.get('selftext', '')}"
        
        positive_words = ['profitable', 'good', 'great', 'excellent', 'amazing', 'pumped', 'moon', 'bullish', 'positive']
        negative_words = ['scam', 'rug', 'bad', 'poor', 'loss', 'dump', 'bearish', 'negative']
        
        score = 0
        for word in positive_words:
            if word in text.lower():
                score += 1
        for word in negative_words:
            if word in text.lower():
                score -= 1
        
        if score > 2:
            return "Very Positive"
        elif score > 0:
            return "Positive"
        elif score < -2:
            return "Very Negative"
        elif score < 0:
            return "Negative"
        else:
            return "Neutral"
    
    def _extract_insights(self, post: Dict) -> List[str]:
        """Extract strategy insights from post."""
        text = post.get('selftext', '')
        insights = []
        
        if 'gas' in text.lower() and 'br' in text.lower():
            insights.append("Mentioned gas bribes")
        
        if 'rpc' in text.lower():
            insights.append("Discussed RPC endpoints")
        
        if 'volume' in text.lower():
            insights.append("Mentioned volume analysis")
        
        if 'strategy' in text.lower():
            insights.append("Contains trading strategy")
        
        return insights
    
    def _is_urgent_opportunity(self, post: Dict) -> bool:
        """Check if post indicates urgent opportunity."""
        text = f"{post['title']} {post.get('selftext', '')}"
        
        urgency_keywords = ['just launched', 'right now', 'live', 'urgent', 'fast', 'quick', 'immediate']
        
        for keyword in urgency_keywords:
            if keyword in text.lower():
                return True
        
        return False
    
    async def trigger_snipe_insights(self, post: Dict):
        """Trigger snipe bot based on Reddit insights."""
        print(f"🚀 Reddit insights suggest opportunity - triggering snipe logic...")
        
        # Extract tokens
        tokens = self._extract_token_symbols(post)
        
        for token in tokens:
            print(f"🎯 Adding {token} to watchlist based on Reddit post")
            # TODO: Add to snipe bot watchlist
        
        print("📋 Snipe bot would execute based on these insights")
    
    def get_stats(self) -> Dict:
        """Get scraper statistics."""
        return {
            "subreddits_monitored": len(self.subreddits),
            "keywords_searched": len(self.keywords),
            "posts_processed": len(self.processed_posts),
            "last_checked": self.last_checked
        }

async def main():
    """Main entry point."""
    scraper = RedditScraper()
    await scraper.monitor()

if __name__ == "__main__":
    asyncio.run(main())