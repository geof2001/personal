#!/usr/bin/env python2.7
import BaseHTTPServer
import SimpleHTTPServer
import SocketServer
import httplib
import re
import subprocess
import sys
import urllib2

PORT = 8000
DOCKER_PS_CMD = 'docker ps --no-trunc=t'
REQUIRED_RUNNING_DOCKER = ('/gateway', '/registrar')
REQUIRED_WEB_SERVER = 'http://localhost:9000/haproxy/stats;csv'


def check_health():
    # docker
    proc = subprocess.Popen(DOCKER_PS_CMD.split(' '), stdout=subprocess.PIPE, )
    dockerps = proc.communicate()[0]
    if proc.returncode != 0:
        return False, dockerps
    all_containers_running = all(container in dockerps for container in REQUIRED_RUNNING_DOCKER)

    try:
        fd = urllib2.urlopen(REQUIRED_WEB_SERVER)
        ret_code = fd.getcode()
        url_content = fd.read()
    except:
        ret_code = httplib.SERVICE_UNAVAILABLE
        url_content = 'ERROR: Unable to fetch from %s' % REQUIRED_WEB_SERVER

    return all_containers_running and ret_code == httplib.OK, "%s\n\n%s" % (dockerps, url_content)


class MyHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        """Respond to a GET request."""

        path = self.path
        path = re.sub('\?.+$', '', path)
        if path == '/healthcheck':
            status, health_msg = check_health()
            if status:
                self.send_response(httplib.OK)
                self.send_header('Content-type', 'text')
                self.end_headers()
                self.wfile.write('PASSED healthcheck:\n%s\n' % health_msg)
                return
            else:
                self.send_response(httplib.SERVICE_UNAVAILABLE)
                self.end_headers()
                self.wfile.write('FAILED healthcheck:\n%s\n' % health_msg)
        elif path in ['/uptime', '/uname', '/whoami', '/ps', '/df', '/docker']:
            path = path.lstrip('/')\
                .replace('ps', 'ps -ef')\
                .replace('df', 'df -k')\
                .replace('docker', 'docker ps --no-trunc=t')
            proc = subprocess.Popen(path.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            msg = proc.communicate()[0]
            if proc.returncode != 0:
                self.send_response(httplib.SERVICE_UNAVAILABLE)
            else:
                self.send_response(httplib.OK)
            self.end_headers()
            self.wfile.write(msg)
        elif path == '/haproxy':
            fd = urllib2.urlopen(REQUIRED_WEB_SERVER)
            ret_code = fd.getcode()
            url_content = fd.read()
            self.send_response(httplib.OK if ret_code == httplib.OK else httplib.SERVICE_UNAVAILABLE)
            self.end_headers()
            self.wfile.write(url_content)
        elif path in ['/cpuinfo', '/meminfo', '/stats']:
            content = open('/proc%s' % path).read()
            self.send_response(httplib.OK)
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(httplib.NOT_FOUND)
            self.end_headers()

if __name__ == '__main__':
    if len(sys.argv) == 2:
        PORT = int(sys.argv[1])

    Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
    httpd = SocketServer.TCPServer(("", PORT), MyHandler)
    print "Serving at port %d (CTRL-C to quit)" % PORT
    httpd.serve_forever()