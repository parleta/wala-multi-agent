#!/bin/bash

# Setup Codecov for AZTM project
# Run this script after getting your token from https://app.codecov.io/gh/eladrave/aztm/settings

echo "Setup Codecov for AZTM"
echo "======================"
echo ""
echo "Please follow these steps:"
echo ""
echo "1. Go to: https://app.codecov.io/gh/eladrave/aztm/settings"
echo "2. Sign in with your GitHub account"
echo "3. Find the repository token (CODECOV_TOKEN)"
echo "4. Copy the token"
echo ""
read -p "Please enter your Codecov token: " CODECOV_TOKEN

if [ -z "$CODECOV_TOKEN" ]; then
    echo "Error: No token provided"
    exit 1
fi

echo ""
echo "Setting Codecov token as GitHub secret..."
gh secret set CODECOV_TOKEN --body "$CODECOV_TOKEN" --repo eladrave/aztm

if [ $? -eq 0 ]; then
    echo "✅ Codecov token successfully set!"
    echo ""
    echo "The CI pipeline will now upload coverage reports to Codecov on each run."
    echo "View coverage at: https://app.codecov.io/gh/eladrave/aztm"
else
    echo "❌ Failed to set Codecov token"
    exit 1
fi