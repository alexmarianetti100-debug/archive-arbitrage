import asyncio
import re
from typing import List, Dict, Optional

class TwitterMonitor:
    """Monitor Twitter for snipe bot signals and token launches."""
    
    def __init__(self):
        self.last_checked = None
        self.ignored_tokens = set()
        self.active_tokens = []
        
    async def monitor(self):
        """Main monitoring loop."""
        print("🔍 Starting Twitter monitoring for snipe signals...")
        
        # Initial scan
        await self.scan_tweets()
        
        # Continue monitoring
        while True:
            await asyncio.sleep(30)  # Check every 30 seconds
            await self.scan_tweets()
            
    async def scan_tweets(self):
        """Scan Twitter for snipe-related content."""
        print("📅 Scanning Twitter for new snipe signals...")
        
        # Simulated tweets (replace with actual API calls)
        tweets = self._fetch_simulated_tweets()
        
        for tweet in tweets:
            await self.process_tweet(tweet)
            
    def _fetch_simulated_tweets(self) -> List[str]:
        """Simulate fetching tweets from Twitter."""
        return [
            "🚨 Sniped token: $SOLSNIPE - 95% absorbed in 2 seconds! 🚀",
            "🔥 New pump.fun token: $MEME2024 - Snipe hit at 0.0001 SOL! 🎉",
            "Twitter bot detected: $NEWTOKEN listing at 100x Volume! 📈",
            "Solset.io just sniped $ALPHA - 98% absorption rate! 🚀",
            "🔥 $TOKENXYZ launched on pump.fun - Sniper bots already active!",
        ]
    
    async def process_tweet(self, tweet: str):
        """Process individual tweet for snipe signals."""
        print(f"📡 Processing tweet: {tweet}")
        
        # Extract token symbol from tweet
        token = self._extract_token_symbol(tweet)
        if not token:
            print(f"❌ No token found in tweet: {tweet}")
            return
            
        # Check if this is a new token
        if token in self.ignored_tokens:
            print(f"🔄 Already processed token {token}, ignoring")
            return
            
        # Check if it's a snipe signal
        if self._is_snip_signal(tweet):
            print(f"🚨 SNIPE ALERT: {token} detected in tweet!")
            # TODO: Trigger snipe bot logic here
            await self.trigger_snipe(token, tweet)
        else:
            print(f"📋 Found token {token} but not a snipe signal")
            
        # Add to processed tokens
        self.active_tokens.append(token)
    
    def _extract_token_symbol(self, tweet: str) -> Optional[str]:
        """Extract token symbol from tweet text."""
        # Look for $TOKEN patterns
        matches = re.findall(r'\$([A-Z0-9]{3,10})', tweet)
        if matches:
            return matches[0]  # Return first token found
        
        # Look for other patterns
        if "token" in tweet.lower():
            # Try to extract from context
            words = tweet.split()
            for i, word in enumerate(words):
                if word.lower() == "token" and i < len(words) - 1:
                    return words[i+1].strip("$.,!?")
        
        return None
    
    def _is_snip_signal(self, tweet: str) -> bool:
        """Determine if tweet is a snipe signal."""
        snipe_keywords = [
            "sniped", "snipe", "sniper", "sniping", "hit", "alert", "detected",
            "absorbed", "launched", "new", "just", "now", "live"
        ]
        
        # Check for snipe-related words
        for kw in snipe_keywords:
            if kw in tweet.lower():
                return True
                
        return False
    
    async def trigger_snipe(self, token: str, tweet: str):
        """Trigger snipe bot logic."""
        print(f"🚀 Triggering snipe for {token} based on tweet:")
        print(f"── {tweet}")
        
        # TODO: Add actual snipe bot trigger logic here
        # For now, just log the action
        print(f"📋 Snipe logic would execute for {token} here")
        
        # Add to ignored tokens to prevent duplicate processing
        self.ignored_tokens.add(token)
    
    def get_stats(self) -> Dict:
        """Get monitoring statistics."""
        return {
            "total_scans": 0,  # TODO: Track actual scans
            "tokens_detected": len(self.active_tokens),
            "ignored_tokens": len(self.ignored_tokens),
            "last_checked": self.last_checked
        }

async def main():
    """Main entry point."""
    monitor = TwitterMonitor()
    await monitor.monitor()

if __name__ == "__main__":
    asyncio.run(main())