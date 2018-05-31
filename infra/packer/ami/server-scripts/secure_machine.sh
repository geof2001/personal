#!/usr/bin/env bash
#

### Set root password
echo '1) Setting the root password...'
sed -i 's#^root:.*#root:\$6\$7WbB6cIb\$OczJuQWj/RlO3XpQ02F1FK.jj7qKba97GC6Jo8sNECXq3zTaE1lVMPvoeTYNBKWnJ80P9YdviXqWzTDft06E60:16378::::::#' /etc/shadow

### Remove unused applications
echo '2) Remove unused applications...'
yum -y -q remove sendmail procmail || true

### Update packages
echo '3) Updating packages...'
sudo yum update -y || true

chkconfig --del sendmail || true

### Some tools can only be run by root
# Comment out if you don't use them in your app scripts
echo 'Last step) Securing tools that can only be run by root (scp, wget, curl, ...)'
sudo chmod 700 /usr/bin/scp /usr/bin/wget /usr/bin/curl
