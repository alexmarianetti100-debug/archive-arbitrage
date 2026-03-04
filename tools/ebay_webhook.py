#!/usr/bin/env python3
"""
eBay Marketplace Account Deletion Webhook

Required for eBay Production API access.
Deploy this somewhere with HTTPS (Vercel, Railway, etc.)

Usage:
    1. Deploy this endpoint
    2. In eBay Developer Portal, set:
       - Endpoint URL: https://your-domain.com/ebay/deletion
       - Verification Token: your-secret-token-here
    3. eBay will verify the endpoint, then you get Production access
"""

from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# Set this to match what you enter in eBay Developer Portal
VERIFICATION_TOKEN = os.getenv("EBAY_VERIFICATION_TOKEN", "archive-arbitrage-delete-2024")


@app.route("/ebay/deletion", methods=["GET", "POST"])
def account_deletion():
    """
    Handle eBay Marketplace Account Deletion notifications.
    
    GET: eBay verification challenge (during setup)
    POST: Actual deletion notification
    """
    
    if request.method == "GET":
        # eBay verification challenge
        challenge_code = request.args.get("challenge_code")
        
        if challenge_code:
            # Hash the challenge with verification token
            import hashlib
            response_hash = hashlib.sha256(
                (challenge_code + VERIFICATION_TOKEN).encode()
            ).hexdigest()
            
            return jsonify({"challengeResponse": response_hash})
        
        return jsonify({"status": "ok", "message": "eBay deletion endpoint ready"})
    
    elif request.method == "POST":
        # Actual deletion notification from eBay
        data = request.json
        
        # Log the deletion request (you'd normally process this)
        print(f"eBay Account Deletion Request: {data}")
        
        # eBay expects 200 OK
        return jsonify({"status": "received"}), 200


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "ebay-webhook"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
