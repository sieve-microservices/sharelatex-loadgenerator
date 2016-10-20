#!/bin/sh

# random source ips to get around rate limiter
set -e

IF=${IF:-eth0:avahi}

for i in $(seq 1 50); do
  ip addr add "172.17.99.$i/16" dev $IF || true
done

iptables -t nat -F RANDSRC || iptables -t nat -N RANDSRC
iptables -t nat -D POSTROUTING -p tcp --dport 80 -j RANDSRC || true
iptables -t nat -I POSTROUTING -p tcp --dport 80 -j RANDSRC

ip=$(getent hosts loadbalancer.local | awk '{print $1}')
for i in $(seq 50 -1 2); do
  iptables -t nat -A RANDSRC -d "$ip" -m statistic --mode nth --every "$i" --packet 0 -j SNAT --to-source 172.17.99.$i
done
