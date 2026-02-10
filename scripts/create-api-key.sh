#!/bin/bash
# Script to create API keys for Voight-Kampff authentication

set -e

# Configuration
AUTH_URL="${AUTH_URL:-https://auth.mon_url.com}"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}   Voight-Kampff API Key Generator${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""

# Get key name
read -p "Enter a name for this API key: " KEY_NAME
if [ -z "$KEY_NAME" ]; then
    echo -e "${RED}Error: Key name cannot be empty${NC}"
    exit 1
fi

# Get user
read -p "Enter username/identifier: " USER
if [ -z "$USER" ]; then
    echo -e "${RED}Error: User cannot be empty${NC}"
    exit 1
fi

# Discover services on the ansible network
echo ""
echo -e "${CYAN}Discovering services on the ansible network...${NC}"

# Get all containers on the ansible network, excluding ansible-traefik, ansible-voight-kampff, and database/redis containers
SERVICES=$(docker network inspect ansible -f '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null | \
    tr ' ' '\n' | \
    grep -v '^$' | \
    grep -v 'ansible-traefik' | \
    grep -v 'ansible-voight-kampff' | \
    grep -v 'postgres' | \
    grep -v 'redis' | \
    grep -v 'db$' | \
    grep -v 'database' | \
    sort)

if [ -z "$SERVICES" ]; then
    echo -e "${YELLOW}Warning: No services found on the ansible network${NC}"
    echo -e "${YELLOW}Make sure your services are running and connected to the 'ansible' network${NC}"
    echo ""
    read -p "Continue with manual scope selection? (y/n): " CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        exit 1
    fi
    MANUAL_MODE=true
else
    MANUAL_MODE=false
    echo -e "${GREEN}Found services:${NC}"
    
    # Create arrays for services
    declare -a SERVICE_NAMES
    declare -a SERVICE_SCOPES
    i=1
    
    while IFS= read -r service; do
        if [ ! -z "$service" ]; then
            # Extract service name from container name
            # Try to extract subdomain from Traefik labels
            SCOPE=$(docker inspect "$service" --format '{{range $key, $value := .Config.Labels}}{{if eq $key "traefik.http.routers.tts.rule"}}tts{{end}}{{if eq $key "traefik.http.routers.stt.rule"}}stt{{end}}{{if eq $key "traefik.http.routers.llm.rule"}}llm{{end}}{{if eq $key "traefik.http.routers.assistant.rule"}}assistant{{end}}{{if eq $key "traefik.http.routers.immich.rule"}}immich{{end}}{{end}}' 2>/dev/null)
            
            # If no scope found from labels, try to extract from router name
            if [ -z "$SCOPE" ]; then
                SCOPE=$(docker inspect "$service" --format '{{range $key, $value := .Config.Labels}}{{if contains $key "traefik.http.routers."}}{{$key}}{{end}}{{end}}' 2>/dev/null | grep -oP 'routers\.\K[^.]+' | head -1)
            fi
            
            # If still no scope, use container name without prefix
            if [ -z "$SCOPE" ]; then
                SCOPE=$(echo "$service" | sed 's/^ansible-//' | sed 's/-service$//' | sed 's/-api$//')
            fi
            
            SERVICE_NAMES[$i]="$service"
            SERVICE_SCOPES[$i]="$SCOPE"
            echo -e "  ${CYAN}[$i]${NC} $service ${YELLOW}(scope: $SCOPE)${NC}"
            ((i++))
        fi
    done <<< "$SERVICES"
    
    TOTAL_SERVICES=$((i-1))
fi

# Get scopes selection
echo ""
echo -e "${BLUE}Select access permissions:${NC}"
echo "  [a] All services (*)"
if [ "$MANUAL_MODE" = false ]; then
    echo "  [s] Select specific services (multi-selection)"
fi
echo "  [c] Custom (manually enter scopes)"
echo ""
read -p "Choice [a/s/c]: " SCOPE_CHOICE

case $SCOPE_CHOICE in
    a|A)
        SCOPES='["*"]'
        SELECTED_DISPLAY="All services (*)"
        ;;
    s|S)
        if [ "$MANUAL_MODE" = true ]; then
            echo -e "${RED}Cannot select services - no services detected${NC}"
            exit 1
        fi
        
        echo ""
        echo -e "${BLUE}Select services (comma-separated numbers, e.g., 1,3,5):${NC}"
        read -p "Services: " SELECTED
        
        if [ -z "$SELECTED" ]; then
            echo -e "${RED}No services selected${NC}"
            exit 1
        fi
        
        # Parse selected services
        declare -a SELECTED_SCOPES
        SELECTED_DISPLAY=""
        IFS=',' read -ra INDICES <<< "$SELECTED"
        for idx in "${INDICES[@]}"; do
            idx=$(echo "$idx" | tr -d ' ')
            if [ "$idx" -ge 1 ] && [ "$idx" -le "$TOTAL_SERVICES" ]; then
                SELECTED_SCOPES+=("${SERVICE_SCOPES[$idx]}")
                SELECTED_DISPLAY="$SELECTED_DISPLAY, ${SERVICE_SCOPES[$idx]}"
            else
                echo -e "${YELLOW}Warning: Index $idx is out of range, skipping${NC}"
            fi
        done
        
        if [ ${#SELECTED_SCOPES[@]} -eq 0 ]; then
            echo -e "${RED}No valid services selected${NC}"
            exit 1
        fi
        
        # Remove leading comma
        SELECTED_DISPLAY=$(echo "$SELECTED_DISPLAY" | sed 's/^, //')
        
        # Convert to JSON array
        SCOPES="["
        for scope in "${SELECTED_SCOPES[@]}"; do
            SCOPES="$SCOPES\"$scope\","
        done
        SCOPES=$(echo "$SCOPES" | sed 's/,$//')"]"
        ;;
    c|C)
        read -p "Enter scopes (comma-separated, e.g., tts,stt,llm): " CUSTOM_SCOPES
        if [ -z "$CUSTOM_SCOPES" ]; then
            echo -e "${RED}No scopes provided${NC}"
            exit 1
        fi
        SELECTED_DISPLAY="$CUSTOM_SCOPES"
        # Convert comma-separated to JSON array
        SCOPES=$(echo "$CUSTOM_SCOPES" | awk -F, '{printf "["; for(i=1;i<=NF;i++){printf "\"%s\"", $i; if(i<NF) printf ","}; printf "]"}')
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Get expiration
echo ""
read -p "Expiration in days (leave empty for no expiration): " EXPIRES_DAYS

# Build JSON payload
if [ -z "$EXPIRES_DAYS" ]; then
    JSON_PAYLOAD=$(cat <<EOF
{
  "key_name": "$KEY_NAME",
  "user": "$USER",
  "scopes": $SCOPES
}
EOF
)
else
    JSON_PAYLOAD=$(cat <<EOF
{
  "key_name": "$KEY_NAME",
  "user": "$USER",
  "scopes": $SCOPES,
  "expires_in_days": $EXPIRES_DAYS
}
EOF
)
fi

echo ""
echo -e "${BLUE}Creating API key...${NC}"

# Make API call
RESPONSE=$(curl -s -X POST "$AUTH_URL/keys" \
    -H "Content-Type: application/json" \
    -d "$JSON_PAYLOAD")

# Check for errors
if echo "$RESPONSE" | grep -q "detail"; then
    echo -e "${RED}Error creating API key:${NC}"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    exit 1
fi

# Parse and display result
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}        API Key Created Successfully!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Key Name:${NC} $KEY_NAME"
echo -e "${BLUE}User:${NC} $USER"
echo -e "${BLUE}Scopes:${NC} $SELECTED_DISPLAY"

if [ ! -z "$EXPIRES_DAYS" ]; then
    echo -e "${BLUE}Expires:${NC} in $EXPIRES_DAYS days"
else
    echo -e "${BLUE}Expires:${NC} Never"
fi

echo ""
echo -e "${GREEN}API Key:${NC}"
API_KEY=$(echo "$RESPONSE" | grep -o '"api_key":"[^"]*' | cut -d'"' -f4)
echo "$API_KEY"
echo ""
echo -e "${RED}⚠️  IMPORTANT: Save this API key now!${NC}"
echo -e "${RED}   It will not be shown again.${NC}"
echo ""
echo -e "${BLUE}Usage example:${NC}"

# Show example for first scope
EXAMPLE_SCOPE=$(echo "$SELECTED_DISPLAY" | cut -d',' -f1 | tr -d ' ')
if [ "$EXAMPLE_SCOPE" = "*" ] || [ "$EXAMPLE_SCOPE" = "All services" ]; then
    EXAMPLE_SCOPE="tts"
fi

echo "curl https://${EXAMPLE_SCOPE}.mon_url.com/api/endpoint \\"
echo "  -H \"Authorization: Bearer $API_KEY\" \\"
echo "  -H \"Content-Type: application/json\""
echo ""

# Show accessible services
echo -e "${BLUE}This key has access to:${NC}"
if [ "$SCOPE_CHOICE" = "a" ] || [ "$SCOPE_CHOICE" = "A" ]; then
    echo "  • All current and future services (*)"
else
    IFS=',' read -ra SCOPE_LIST <<< "$SELECTED_DISPLAY"
    for scope in "${SCOPE_LIST[@]}"; do
        scope=$(echo "$scope" | tr -d ' ')
        echo "  • https://${scope}.mon_url.com"
    done
fi
echo ""
