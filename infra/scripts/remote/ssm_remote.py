import os
import sys
import subprocess
import datetime
"""
This is a python command that can make flamegraphs on ECS host machines.
The command is:

> sudo python <docker-id> <run-time> flamegraph
"""


def start():
    num_args = len(sys.argv)
    print('num_args={}'.format(num_args))
    if num_args<4:
        print('Needs 3 args')
    docker_id = sys.argv[1]
    run_time = sys.argv[2]
    type = sys.argv[3]

    comment = 'remote'
    if num_args==5:
        comment = sys.argv[4]

    if type == 'flamegraph':
        fg_script(docker_id, run_time, comment)
    else:
        print('Type must be "flamegraph" was: {}'.type)


def fg_script(docker_id, run_time, comment):

    now = datetime.datetime.now()
    name_post_fix = '{}-{}-{}'.format(comment, now.hour,now.minute)
    file_name = 'run_{}.log'.format(name_post_fix)
    fd = open(file_name, 'w')

    output(fd, 'docker_id = {}'.format(docker_id))
    output(fd, 'run_time = {}'.format(run_time))

    # Some environment info
    bash_test = sys_call(fd, 'echo a;echo b')
    output(fd, 'bash_test= _{}_'.format(bash_test))

    # set_before = sys_call(fd, 'set | grep BASH')
    # check_call(fd, 'set > set_before_{}.txt'.format(name_post_fix))
    # output(fd, set_before)
    # set_path_before = sys_call(fd, 'set | grep PATH')
    # output(fd, set_path_before)

    whoami = sys_call(fd, 'whoami')
    output(fd, 'whoami=_{}_'.format(whoami))
    sys_call(fd, 'source /home/ec2-user/.bash_profile')
    check_call(fd, 'export PATH=/usr/local/bin:/bin:/usr/bin:/usr/local/sbin:/usr/sbin:/sbin:/home/ec2-user/.local/bin:/home/ec2-user/bin')
    check_call(fd, 'export BASH=/bin/bash')

    output(fd, '========AFTER source=======')
    check_call(fd, 'set > set_after_{}.txt'.format(name_post_fix))
    # set_after = sys_call(fd, 'set | grep BASH'.format(name_post_fix))
    # output(fd, set_after)
    set_path_after = sys_call(fd, 'set | grep PATH')
    output(fd, set_path_after)

    pid = sys_call(fd, "docker inspect --format '{{.State.Pid}}' "+docker_id)
    pid = pid.strip('\n')
    output(fd, "pid=_{}_".format(pid))

    # check_call(fd, 'perf record -F 99 -g -p {} -- sleep {}'.format(pid, run_time))
    check_call(fd, 'perf record -F 99 -o /home/ec2-user/perf.data -g -p {} -- sleep {}'.format(pid, run_time))

    find_data = sys_call(fd, 'find / -type f -name perf.data')
    output(fd, "find_data=_{}_".format(find_data))

    sys_call(fd, 'docker cp /util/perf-map-agent {}:/util'.format(docker_id))
    sys_call(fd, 'docker exec {} /util/perf-map-agent/bin/create-java-perf-map.sh 1'.format(docker_id))
    jdk_dir = sys_call(fd, 'docker exec {} ls /opt | grep jdk'.format(docker_id))
    jdk_dir = jdk_dir.strip('\n')
    output(fd, 'jdk_dir = _{}_'.format(jdk_dir))

    sys_call(fd, 'mkdir -p /opt/{}/jre/lib/amd64/server'.format(jdk_dir))
    sys_call(fd, 'docker cp {}:/tmp/perf-1.map /tmp/perf-{}.map'.format(docker_id, pid))
    sys_call(fd, 'docker cp {}:/opt/{}/jre/lib/amd64/server/libjvm.so /opt/{}/jre/lib/amd64/server/libjvm.so'.format(docker_id, jdk_dir, jdk_dir))
    sys_call(fd, 'docker cp {}:/opt/{}/jre/lib/amd64/libzip.so /opt/{}/jre/lib/amd64/libzip.so'.format(docker_id, jdk_dir, jdk_dir))
    sys_call(fd, 'docker cp {}:/opt/{}/jre/lib/amd64/libverify.so /opt/{}/jre/lib/amd64/libverify.so'.format(docker_id, jdk_dir, jdk_dir))
    sys_call(fd, 'docker cp {}:/opt/{}/jre/lib/amd64/libjava.so /opt/{}/jre/lib/amd64/libjava.so'.format(docker_id, jdk_dir, jdk_dir))
    sys_call(fd, 'docker cp {}:/opt/{}/jre/lib/amd64/libnio.so /opt/{}/jre/lib/amd64/libnio.so'.format(docker_id, jdk_dir, jdk_dir))
    sys_call(fd, 'docker cp {}:/opt/{}/jre/lib/amd64/libnet.so /opt/{}/jre/lib/amd64/libnet.so'.format(docker_id, jdk_dir, jdk_dir))
    sys_call(fd, 'docker cp {}:/opt/{}/jre/lib/amd64/libsunec.so /opt/{}/jre/lib/amd64/libsunec.so'.format(docker_id, jdk_dir, jdk_dir))
    sys_call(fd, 'perf script | /usr/local/flamegraph/stackcollapse-perf.pl --kernel | /usr/local/flamegraph/flamegraph.pl --color=java --hash > perf-{}.svg'.format(pid))
    sys_call(fd, 'rm /tmp/perf-{}.map'.format(pid))

    ls_after = sys_call(fd, 'ls -ltra | grep perf')
    output(fd, ls_after)

    sys_call(fd, 'rm perf.data')

    svg_file = 'perf-{}.svg'.format(pid)
    dest_svg_file_name = 'perf-{}-{}.svg'.format(pid, name_post_fix)

    find_svg_file = sys_call(fd, 'find / -type f -name {}'.format(svg_file))
    output(fd, "find_svg_file=_{}_".format(find_svg_file))


    sys_call(fd, 'aws s3 cp /home/ec2-user/{} s3://sr-infra-slackbud-images-us-west-2/svg/{}'
                 ' --acl public-read'.format(svg_file, dest_svg_file_name))

    fd.close()


def sys_call(fd, command):
    try:
        output(fd, '> '+command)
        p = subprocess.Popen([command], stdout=subprocess.PIPE, shell=True)
        # p = subprocess.Popen([command], stdout=subprocess.PIPE)
        return p.stdout.read()
    except Exception as ex:
        error_lines = '\n{}\nError: {}'.format(command, ex.message)
        with open("error.txt", "a") as error_file:
            error_file.write(error_lines)
        return "ERROR: {}".format(ex.message)


def check_call(fd, command):
    try:
        parts = command.split()

        output(fd, 'call> {}'.format(parts))
        return_code = subprocess.check_call(parts)
        output(fd, 'check_call returned: {}'.format(return_code))
    except Exception as ex:
        error_lines = '\n{}\nError: {}'.format(command, ex.message)
        with open("error.txt", "a") as error_file:
            error_file.write(error_lines)
        return "ERROR: {}".format(ex.message)


def output(fd, line):
    print(line)
    fd.write('{}\n'.format(line))


if __name__ == '__main__':
    start()
