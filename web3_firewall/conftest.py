# conftest.py — pytest configuration for the web3_firewall package
import sys
import os

# Ensure the web3_firewall root is on sys.path so all modules resolve correctly
# when running pytest from the web3_firewall/ directory.
sys.path.insert(0, os.path.dirname(__file__))

# Also expose the training_pipeline directory so tests that import from
# data_loader (e.g. for TRANSACTION_FEATURES) work without installation.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "training_pipeline"))
# Fallback: if running from front/ with training files flat alongside web3_firewall/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
