"""
Vercel Serverless Function for eBay Marketplace Account Deletion Webhook

Required for eBay Production API access.

To deploy:
    1. npm i -g vercel
    2. vercel login
    3. vercel --prod
    4. In eBay Developer Portal, set:
       - Endpoint URL: https://your-domain.vercel.app/ebay/deletion
       - Verification Token: archive-arbitrage-delete-2024
    5. eBay will verify the endpoint, then you get Production access
"""

from flask import Flask, request, jsonify
import os
import hashlib

app = Flask(__name__)

# Set this to match what you enter in eBay Developer Portal
VERIFICATION_TOKEN = os.getenv("EBAY_VERIFICATION_TOKEN", "abc123")


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
        
        # Debug logging
        print(f"[DEBUG] GET request to /ebay/deletion")
        print(f"[DEBUG] challenge_code: {challenge_code}")
        print(f"[DEBUG] VERIFICATION_TOKEN: {VERIFICATION_TOKEN}")
        print(f"[DEBUG] All args: {dict(request.args)}")
        
        if challenge_code:
            # Hash the challenge with verification token
            response_hash = hashlib.sha256(
                (challenge_code + VERIFICATION_TOKEN).encode()
            ).hexdigest()
            
            print(f"[DEBUG] challengeResponse: {response_hash}")
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
    return jsonify({
        "status": "healthy", 
        "service": "archive-arbitrage-ebay-webhook",
        "ready_for": "eBay Production API verification"
    })


# Vercel serverless handler
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        with app.test_client() as client:
            response = client.get(self.path)
            self.send_response(response.status_code)
            for key, value in response.headers:
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response.data)
    
    def do_POST(self):
        with app.test_client() as client:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            response = client.post(
                self.path,
                data=body,
                content_type=self.headers.get('Content-Type', 'application/json')
            )
            self.send_response(response.status_code)
            for key, value in response.headers:
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response.data)
