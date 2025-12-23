#!/bin/bash

# ============ DARK TUNNEL FULL VPN ============
SOCKS_PORT=1080
BUG_HOST="BUG_HOST"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Run with:  sudo ~/full-vpn.sh${NC}"
    exit 1
fi

# Get network info
DEFAULT_GW=$(ip route | grep default | awk '{print $3}' | head -1)
DEFAULT_IF=$(ip route | grep default | awk '{print $5}' | head -1)
BUG_IP=$(dig +short $BUG_HOST | grep -E '^[0-9]+\.' | head -1)

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}   FULL SYSTEM VPN via Dark Tunnel${NC}"
echo -e "${GREEN}================================================${NC}"
echo -e "${CYAN}[i] Gateway: $DEFAULT_GW via $DEFAULT_IF${NC}"
echo -e "${CYAN}[i] Bug Host: $BUG_HOST ($BUG_IP)${NC}"

cleanup() {
    echo -e "\n${YELLOW}[*] Restoring network... ${NC}"
    pkill badvpn-tun2socks 2>/dev/null
    ip route del default 2>/dev/null
    ip route del $BUG_IP/32 2>/dev/null
    ip route add default via $DEFAULT_GW dev $DEFAULT_IF 2>/dev/null
    ip link set tun0 down 2>/dev/null
    ip tuntap del tun0 mode tun 2>/dev/null
    echo -e "${GREEN}[+] Network restored! ${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# Check SOCKS is running (check if port is open)
echo -e "${YELLOW}[*] Checking SOCKS proxy on port $SOCKS_PORT...${NC}"

# Use netcat to check if port is open
if !  nc -z 127.0.0.1 $SOCKS_PORT 2>/dev/null; then
    echo -e "${RED}[-] Port $SOCKS_PORT not open!${NC}"
    echo -e "${RED}    Start dark-tunnel-final.py first${NC}"
    exit 1
fi

echo -e "${GREEN}[+] SOCKS port is open!${NC}"

# Test SOCKS proxy works
echo -e "${YELLOW}[*] Testing SOCKS connection...${NC}"
TEST_IP=$(curl -s --max-time 15 -x socks5h://127.0.0.1:$SOCKS_PORT ifconfig.me 2>/dev/null)
if [ -z "$TEST_IP" ]; then
    echo -e "${YELLOW}[!] Could not verify VPN IP, but port is open.  Continuing...${NC}"
else
    echo -e "${GREEN}[+] SOCKS working!  VPN IP: $TEST_IP${NC}"
fi

# Setup TUN device
echo -e "${YELLOW}[*] Setting up TUN device...${NC}"
ip tuntap del tun0 mode tun 2>/dev/null
ip tuntap add dev tun0 mode tun
ip addr add 10.0.0.1/24 dev tun0
ip link set tun0 up

# Start tun2socks
echo -e "${YELLOW}[*] Starting tun2socks...${NC}"
badvpn-tun2socks --tundev tun0 \
    --netif-ipaddr 10.0.0.2 \
    --netif-netmask 255.255.255.0 \
    --socks-server-addr 127.0.0.1:$SOCKS_PORT \
    --loglevel none &
sleep 2

# Setup routing
echo -e "${YELLOW}[*] Setting up routes...${NC}"
ip route add $BUG_IP/32 via $DEFAULT_GW dev $DEFAULT_IF
ip route del default
ip route add default via 10.0.0.2 dev tun0

# Verify
sleep 2
FINAL_IP=$(curl -s --max-time 15 ifconfig.me 2>/dev/null)
echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}   FULL SYSTEM VPN ACTIVE! ${NC}"
echo -e "${GREEN}================================================${NC}"
if [ -n "$FINAL_IP" ]; then
    echo -e "  Your IP: ${CYAN}$FINAL_IP${NC}"
else
    echo -e "  Your IP: ${YELLOW}(checking...)${NC}"
fi
echo -e "  All traffic via:  ${CYAN}$BUG_HOST${NC}"
echo -e "${YELLOW}  Press Ctrl+C to disconnect${NC}"
echo -e "${ORANGE}  Script By Genith-Utkarsh${NC}"
echo -e "${GREEN}================================================${NC}"

# Keep running
while true; do
    sleep 30
done
