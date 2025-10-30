#!/usr/bin/env python3
"""Quick test to verify Firestore connection"""

import os
from google.cloud import firestore

print(f"USE_FIRESTORE env var: {os.getenv('USE_FIRESTORE')}")
print(f"GOOGLE_APPLICATION_CREDENTIALS: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'Not set (will use gcloud auth)')}")

try:
    db = firestore.Client()
    print("✅ Firestore client created successfully")
    
    # Try to write a test document
    test_ref = db.collection("_test").document("test_doc")
    test_ref.set({"test": "data", "timestamp": firestore.SERVER_TIMESTAMP})
    print("✅ Successfully wrote test document")
    
    # Read it back
    doc = test_ref.get()
    if doc.exists:
        print(f"✅ Successfully read test document: {doc.to_dict()}")
    
    # Clean up
    test_ref.delete()
    print("✅ Cleaned up test document")
    
    print("\n🎉 Firestore is working correctly!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nTroubleshooting:")
    print("1. Run: gcloud auth application-default login")
    print("2. Make sure Firestore is enabled in your GCP project")
    print("3. Check: gcloud config get-value project")

