#coding=gbk

import shlex
import subprocess
import time
import uuid
import os
from urllib2 import urlopen
import platform

target = '8.8.8.8'
processor = '10.0.63.200'
processor_port = 8001

def find_ip():
    my_ip = urlopen('http://ip.42.pl/raw').read()
    print 'Local address is %s' % my_ip
    return my_ip

def chcp():
    r = os.popen('chcp')
    lines = r.readlines()
    info = lines[0].split()
    code = info[len(info)-1]
    if code == '437':
        lang = 'English'
    elif code == '936':
        lang = 'Chinese'
    else:
        lang = 'Others'
    print 'Your system language is ' + lang
    return code

def write_base(fi):    
    fi.write('Target: %s\n' % target)
    fi.write('LocalAddress: %s\n' % find_ip())
    fi.write('Platform: %s\n' % platform.platform())

def traceroute(code, logfile):
    cmd = 'tracert -d -h 64 %s' % target
    fi = open(logfile, 'w+')
    write_base(fi)
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
    while True:
        out = p.stdout.readline()
        if out == '':
            if p.poll is not None:
                break
        else:
            outs = out.split()
            if len(outs) == 0:
                continue
            if not outs[0].isdigit():
                continue
            data = outs[0]
            start = 1
            for i in range(3):
                if outs[start] == '*':
                    data += ' -1'
                    start += 1
                else:
                    if outs[start] == '<1':
                        data += ' 0'
                    else:
                        data += ' ' + outs[start]
                    start += 2
            addr = outs[start]
            if code == '437':
                miss_str = 'Request timed out'
            elif code == '936':
                miss_str = '请求超时'
            if addr.startswith(miss_str):
                addr = '0.0.0.0'
            data += ' ' + addr
            print out
            fi.write(data + '\n')
            fi.flush()
    fi.close()

def ping(code, logfile):
    cmd = 'ping -t %s' % target
    fi = open(logfile, 'w+')
    write_base(fi)
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
    seq = 1
    while True:
        out = p.stdout.readline()
        if out == '':
            if p.poll is not None:
                break
        else:
            if code == '437':
                hit_str = 'Relay from'
                miss_str = 'Request timed out'
            elif code == '936':
                hit_str = '来自'
                miss_str = '请求超时'
            if out.startswith(hit_str):
                print out
                data = '%d ' % seq
                outs = out.split()
                byts = outs[3].split('=', 1)[1]
                delay = outs[4].split('=', 1)[1].split('ms', 1)[0]
                ttl = outs[5].split('=', 1)[1]
                data += '%s %s %s' % (byts, delay, ttl)
                seq += 1
            elif out.startswith(miss_str):
                print out
                data = '%d ' % seq
                data += '0 -1 0'
                seq += 1
            else:
                continue
            fi.write(data + '\n')
            fi.flush()
    fi.close()

def upload(logfile):
    cmd_curl = 'curl -T "%s" "http://%s:%d/file/"' % (logfile, processor, processor_port)
    print cmd_curl
    args = shlex.split(cmd_curl)
    p = subprocess.Popen(cmd_curl)
    p.wait()
    return p.returncode

if __name__ == '__main__':
    print 'PALLN test starting...'
    print 'Target is %s' % target

    code = chcp()

    tid = uuid.uuid1()

    trlog = 'tracert_%s.log' % tid
    traceroute(code, trlog)
    ret = 1
    count = 0
    while ret != 0:
        count += 1
        if count == 4:
            break
        ret = upload(trlog)
        if ret == 0:
            os.system('del %s' % trlog)
        

    pinglog = 'ping_%s.log' % tid
    ping(code, pinglog)
    ret = 1
    count = 0
    while ret != 0:
        count += 1
        if count == 4:
            break
        ret = upload(pinglog)
        if ret == 0:
            os.system('del %s' % pinglog)
