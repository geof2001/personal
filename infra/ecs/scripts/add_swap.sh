#!/bin/sh

set -e
set -x

total_kb_ram=`awk '/MemTotal/ {print $2}' /proc/meminfo`
if [ $total_kb_ram -lt 8000000 ]; then
  SWAP_MB=3000
elif [ $total_kb_ram -gt 32000000 ]; then
  SWAP_MB=8000
else
  SWAP_MB=`echo "$total_kb_ram * 0.25 / 1024" | bc -l`
  SWAP_MB=`printf '%0.f' $SWAP_MB`
fi

add_swap() {
  swap_file=$1/swapfile
  echo "Adding $swap_file..."
  rm -f $swap_file
  set -x
  dd if=/dev/zero of=$swap_file bs=1M count=$SWAP_MB
  chown root:root $swap_file
  chmod 600 $swap_file

  mkswap $swap_file
  swapon $swap_file
  added_swap=1
  set +x
}

swapoff -a

added_swap=0
# xvda = ELB
# xvdcz = special Docker/ECS partition
lsblk | grep '^xvd' | egrep -v '^(xvda|xvdcz)' | while read blk; do
  dev=`echo $blk | awk '{print $1'}`
  mount_point=`echo $blk | awk '{print $7}'`
  if [ "$mount_point" = "" ]; then
    mount_point="/mnt/ephemeral_$dev"
    mkdir -p $mount_point
    mount /dev/$dev $mount_point
  fi
  add_swap $mount_point
done

# This is probably ELB, it'll be slow
if [ "$added_swap" = 0 -a "`lsblk | grep '^xvd' | egrep -v '^(xvda|xvdcz)'`" = "" ]; then
  mount_point="/mnt"
  mkdir -p $mount_point
  add_swap $mount_point
fi

swapon -a
echo "Done adding swap."
