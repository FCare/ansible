#!/bin/bash
# Script to list all API keys

set -e

# Configuration
AUTH_URL="${AUTH_URL:-https://auth.mon_url.com}"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}   Voight-Kampff API Keys${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""

# Fetch API keys
RESPONSE=$(curl -s "$AUTH_URL/keys")

# Check for errors
if echo "$RESPONSE" | grep -q "detail"; then
    echo -e "${RED}Error fetching API keys:${NC}"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    exit 1
fi

# Display results
echo "$RESPONSE" | python3 -c "
import sys
import json
from datetime import datetime

try:
    keys = json.load(sys.stdin)
    
    if not keys:
        print('${YELLOW}No API keys found.${NC}')
        sys.exit(0)
    
    for key in keys:
        print('─' * 60)
        print(f'ID: {key[\"id\"]}')
        print(f'Name: ${GREEN}{key[\"key_name\"]}${NC}')
        print(f'User: {key[\"user\"]}')
        print(f'Scopes: {', '.join(key[\"scopes\"])}')
        
        # Status
        status = '${GREEN}Active${NC}' if key['is_active'] else '${RED}Disabled${NC}'
        print(f'Status: ' + status)
        
        # Dates
        created = datetime.fromisoformat(key['created_at'].replace('Z', '+00:00'))
        print(f'Created: {created.strftime(\"%Y-%m-%d %H:%M:%S\")}')
        
        if key['last_used']:
            last_used = datetime.fromisoformat(key['last_used'].replace('Z', '+00:00'))
            print(f'Last Used: {last_used.strftime(\"%Y-%m-%d %H:%M:%S\")}')
        else:
            print('Last Used: ${YELLOW}Never${NC}')
        
        if key['expires_at']:
            expires = datetime.fromisoformat(key['expires_at'].replace('Z', '+00:00'))
            now = datetime.now(expires.tzinfo)
            if expires < now:
                print(f'Expires: ${RED}{expires.strftime(\"%Y-%m-%d %H:%M:%S\")} (EXPIRED)${NC}')
            else:
                days_left = (expires - now).days
                print(f'Expires: {expires.strftime(\"%Y-%m-%d %H:%M:%S\")} ({days_left} days left)')
        else:
            print('Expires: ${GREEN}Never${NC}')
        
        print()
    
    print('─' * 60)
    print(f'Total keys: {len(keys)}')

except Exception as e:
    print(f'${RED}Error parsing response: {e}${NC}')
    sys.exit(1)
" || (echo -e "${RED}Error: Python3 is required to parse JSON${NC}" && exit 1)
