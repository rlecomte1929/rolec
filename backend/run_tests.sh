#!/bin/bash
# Run backend tests

echo "Installing test dependencies..."
pip install -q -r test_requirements.txt

echo ""
echo "Running backend tests..."
echo "========================"
python -m pytest tests/ -v --tb=short

echo ""
echo "Tests complete!"
