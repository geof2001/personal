#!/bin/sh
#
# This script is called by dynamic_configs.sh (which is called by cloud-init)
#

if [ -f /etc/sudoers.d/cloud-init ]; then
    sed -i 's|NOPASSWD|PASSWD|g' /etc/sudoers.d/cloud-init
    echo '# sudo disabled by /usr/local/bin/disable_sudo.sh' >> /etc/sudoers.d/cloud-init
fi
