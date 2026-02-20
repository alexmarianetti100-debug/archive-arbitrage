# eBay Production API Setup Guide

## Overview
To get Production eBay API keys (required for real sold data), you need to deploy an account deletion webhook endpoint.

## Quick Deploy (Vercel)

### 1. Install Vercel CLI
```bash
npm i -g vercel
```

### 2. Login to Vercel
```bash
vercel login
```

### 3. Deploy the Webhook
```bash
cd ~/clawd/projects/archive-arbitrage
vercel --prod
```

You'll get a URL like: `https://archive-arbitrage-xyz123.vercel.app`

### 4. Configure eBay Developer Portal

1. Go to: https://developer.ebay.com/my/keys
2. Find your app
3. Set **Marketplace Account Deletion Endpoint**:
   - URL: `https://your-domain.vercel.app/ebay/deletion`
   - Verification Token: `archive-arbitrage-delete-2024`
4. Save

### 5. eBay Verification
- eBay will send a GET request to verify the endpoint
- The endpoint will respond with the hashed challenge
- Once verified, you get Production API access

### 6. Get Production Keys
- After verification, eBay provides Production App ID, Cert ID, Dev ID
- Add these to your `.env` file:
```
EBAY_PROD_APP_ID=your_prod_app_id
EBAY_PROD_CERT_ID=your_prod_cert_id
EBAY_PROD_DEV_ID=your_prod_dev_id
EBAY_PROD_AUTH_TOKEN=your_prod_auth_token
```

## Alternative: Railway

If Vercel doesn't work:

```bash
npm i -g @railway/cli
railway login
cd ~/clawd/projects/archive-arbitrage
railway init
railway up
```

## Testing the Webhook

Once deployed, test with:
```bash
curl https://your-domain.vercel.app/
# Should return: {"status": "healthy", ...}

curl "https://your-domain.vercel.app/ebay/deletion?challenge_code=test123"
# Should return: {"challengeResponse": "..."}
```

## Next Steps After Production Access

1. Update `scrapers/ebay_sold.py` with Production keys
2. Run `python scrapers/ebay_sold.py` to get real eBay sold data
3. This feeds into the multi-platform pricer for better market pricing

## Troubleshooting

- **Challenge fails**: Make sure verification token matches exactly
- **Endpoint not reachable**: Check Vercel logs with `vercel logs --tail`
- **SSL errors**: eBay requires HTTPS (Vercel provides this automatically)
