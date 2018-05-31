#!/usr/bin/env python
#
# This script calls docker ps, and adds jmx entries when required.

import os
import re
import subprocess
import yaml

JMX_PORTS = [7199]  # Roku pre-agreed convention is to use 7199 as the JMX port
HAPROXY_PORTS = [8440, 8442, 8444, 8446, 8448]  # Roku pre-agreed convention
DOCKER_PS_CMD = 'docker ps --no-trunc'
DOCKER_INSPECT_CMD = ('docker inspect -f \'{{index .Config.Labels '
                      '"com.amazonaws.ecs.container-name"}}\'')
DATADOG_PATH = '/etc/dd-agent'
JMX_YAML = DATADOG_PATH + '/conf.d/jmx.yaml'
TOMCAT_YAML = DATADOG_PATH + '/conf.d/tomcat.yaml'
HAPROXY_YAML = DATADOG_PATH + '/conf.d/haproxy.yaml'
HAPROXY_URL = 'http://localhost:{port}/haproxy/stats;csv'

for _path in (TOMCAT_YAML, HAPROXY_YAML):
    if not os.path.exists(_path + '.example'):
        raise Exception("Unable to find %s.example" % _path)

mapping_start = {}  # mapping of key to start-end index
mapping_end = {}  # mapping of key to start-end index


def extract_key(key, line):
    start_idx = mapping_start[key]
    end_idx = mapping_end[key] if key in mapping_end else len(line)
    return line[start_idx:end_idx].rstrip('\n').rstrip(' ').lstrip(' ')


def get_docker_servername2jmxport_and_haproxyports():
    servername_to_jmxport = {}
    haproxyports = []
    for line in subprocess.Popen(
            DOCKER_PS_CMD, shell=True, stdout=subprocess.PIPE).stdout.readlines():
        #print line,
        if not mapping_start:
            line = line.rstrip("\n")
            prev_key = None
            for key in re.split('\s\s+', line):
                curr_key_idx = line.index(key)
                mapping_start[key] = curr_key_idx
                if prev_key is not None:
                    mapping_end[prev_key] = curr_key_idx
                prev_key = key
            #print "1: %s" % mapping_start
            #print "2: %s" % mapping_end
            continue

        ports_info = re.split('\s*,\s*', extract_key('PORTS', line))
        longfullname = extract_key('NAMES', line)
        # ecs-universal-haproxy-10-universalhaproxy-a28d96afa5ae9faaf301
        # ecs-linearapi-13-linearapi-f2abbdfcacffa3842200
        servername_taskname = re.split('\-\d+\-', longfullname, 1)
        if len(servername_taskname) != 2 or servername_taskname[0] == '':
            continue
        m = re.match('^ecs\-(.+)', servername_taskname[0], re.IGNORECASE)
        if not m:
            continue

        servername = m.group(1)
        servername2 = ' '.join(subprocess.Popen(
            DOCKER_INSPECT_CMD + ' ' + longfullname,
            shell=True,
            stdout=subprocess.PIPE).stdout.readlines()).replace('\n','')
        servername = servername2 or servername

        for port_info in ports_info:
            # port_info = ''0.0.0.0:7106->7199/tcp'
            m = re.search(':(\d+)\->(\d+)', port_info)
            if not m:
                continue
            host_port, container_port = m.group(1, 2)
            host_port, container_port = int(host_port), int(container_port)
            if container_port in JMX_PORTS:
                servername_to_jmxport[servername] = host_port
            elif host_port in HAPROXY_PORTS:
                haproxyports.append(host_port)
    haproxyports.append(9000) #port 9000 in internal proxy manually added because it's not a port exposed by a docker service
    return servername_to_jmxport, sorted(haproxyports)


def get_existing_servername2jmxport():
    servername_to_jmxport = {}
    if not os.path.exists(TOMCAT_YAML):
        return servername_to_jmxport

    tc_config = yaml.load(open(TOMCAT_YAML).read())
    if 'instances' not in tc_config or type(tc_config['instances']) != list:
        return {}
    for instance in tc_config['instances']:
        try:
            port = int(instance['port'])
            service_name = instance['tags']['serviceName']
            servername_to_jmxport[service_name] = port
        except KeyError:
            print "Instance entry is not valid:%s" % instance

    return servername_to_jmxport


def get_existing_haproxyports():
    haproxyports = []
    if not os.path.exists(HAPROXY_YAML):
        return haproxyports
    with open(HAPROXY_YAML) as fd:
        for line in fd:
            m = re.search('\-\s*url: http://localhost:(\d+)', line, re.I)
            if m:
                port = int(m.group(1))
                haproxyports.append(port)
    return sorted(haproxyports)


def update_tomcat_yaml(servername_to_jmxport):
    update_generic_yaml(TOMCAT_YAML, servername_to_jmxport, """
  - host: localhost
    port: {port}
    tags:
      serviceName: {server_name}
      com.amazonaws.ecs.container-name: {server_name}\n\n""")


def update_jmx_yaml(servername_to_jmxport):
    update_generic_yaml(JMX_YAML, servername_to_jmxport, """
  - host: localhost
    port: {port}
    tags:
      serviceName: {server_name}
      com.amazonaws.ecs.container-name: {server_name}
    conf:
      - include:
          domain: org.eclipse.jetty.util.thread\n\n""")


def update_generic_yaml(yaml_file, servername_to_jmxport, line_output):
    # fill in content
    yaml_content = yaml.load(open(yaml_file + '.example').read())
    try:
        del yaml_content['instances']
    except KeyError:
        pass
    content = yaml.dump(yaml_content, default_flow_style=False)

    with open(yaml_file, 'w') as wd:
        wd.write('# === This file is auto generated by update_datadog_on_ecs.py ===\n')
        wd.write('instances:\n')
        for server_name in sorted(servername_to_jmxport):
            port = servername_to_jmxport[server_name]
            wd.write(line_output.format(
                port=port, server_name=server_name))
        wd.write(''.join(content))

    subprocess.call("chown {owner} {yaml}".format(
        owner='dd-agent',
        yaml=yaml_file
    ), shell=True)


def update_haproxyyaml(haproxyports):
    with open(HAPROXY_YAML, 'w') as wd:
        wd.write("""init_config:

instances:
""")
        for port in haproxyports:
            url = HAPROXY_URL.format(port=port)
            wd.write("  - url: %s\n" % url)
        wd.write('\n')
    subprocess.call("chown {owner} {yaml}".format(
        owner='dd-agent',
        yaml=HAPROXY_YAML
    ), shell=True)


def backup_file(fname):
    cp_ret = 0
    if os.path.exists(fname):
        cp_ret = subprocess.call(
            "cp %s %s" % (fname, fname + '.bak'), shell=True)
    return cp_ret


if __name__ == '__main__':
    datadog_servername2jmxport, datadog_haproxyports = \
        (get_existing_servername2jmxport(),
         get_existing_haproxyports())
    docker_servername2jmxport, docker_haproxyports = \
        get_docker_servername2jmxport_and_haproxyports()

    need_to_restart_dd, cp_ret = False, 0
    if datadog_servername2jmxport != docker_servername2jmxport:
        print "Old %s: %s" % (TOMCAT_YAML, datadog_servername2jmxport)
        print "New %s: %s" % (TOMCAT_YAML, docker_servername2jmxport)
        cp_ret += backup_file(TOMCAT_YAML)
        update_jmx_yaml(docker_servername2jmxport)
        update_tomcat_yaml(docker_servername2jmxport)
        need_to_restart_dd = True
    if datadog_haproxyports != docker_haproxyports:
        print "Old %s: %s" % (HAPROXY_YAML, datadog_haproxyports)
        print "New %s: %s" % (HAPROXY_YAML ,docker_haproxyports)
        cp_ret += backup_file(HAPROXY_YAML)
        update_haproxyyaml(docker_haproxyports)
        need_to_restart_dd = True

    if need_to_restart_dd and cp_ret == 0:
        restart_ret = subprocess.call("/etc/init.d/datadog-agent restart",
                                      shell=True)
        if restart_ret != 0:
            print "ERROR: restart failed, reverting yaml file..."
            subprocess.call("cp %s %s" % (TOMCAT_YAML + '.bak', TOMCAT_YAML),
                            shell=True)
            subprocess.call("cp %s %s" % (HAPROXY_YAML + '.bak', HAPROXY_YAML),
                            shell=True)
