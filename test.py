#coding=gbk

import subprocess
import time
import shortuuid
import os
import platform
import httplib
import json

target = '8.8.8.8'
processor = '10.0.63.200'
processor_port = 8001

def find_ip_loc():
    cli = httplib.HTTPConnection('ipinfo.io', 80, timeout=30)
    cli.request('GET', 'http://ipinfo.io')
    res = cli.getresponse()
    data = res.read()
    print data
    ipinfo = json.loads(data)
    return ipinfo

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

def writebase(logfile):
    fi = open(logfile, 'w+')
    ipinfo = find_ip_loc()
    baseinfo = dict()
    baseinfo['target'] = target
    baseinfo['ip'] = ipinfo['ip']
    baseinfo['location'] = ipinfo['city'] + ' ' + ipinfo['region'] + ' ' + ipinfo['country']
    baseinfo['org'] = ipinfo['org']
    baseinfo['platform'] = platform.platform()
    baseinfo['time'] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
    jsonstr = json.dumps(baseinfo)
    fi.write(jsonstr)
    fi.close()

def traceroute(code, logfile):
    cmd = 'tracert -d -h 64 %s' % target
    fi = open(logfile, 'w+')
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
                    data += ',-1'
                    start += 1
                else:
                    if outs[start] == '<1':
                        data += ',0'
                    else:
                        data += ',' + outs[start]
                    start += 2
            addr = outs[start]
            if code == '437':
                miss_str = 'Request timed out'
            elif code == '936':
                miss_str = '请求超时'
            if addr.startswith(miss_str):
                addr = '0.0.0.0'
            data += ',' + addr
            print out
            fi.write(data + '\n')
            fi.flush()
    fi.close()

def ping(code, logfile):
    cmd = 'ping -t %s' % target
    fi = open(logfile, 'w+')
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
                data = '%d,' % seq
                outs = out.split()
                byts = outs[3].split('=', 1)[1]
                delay = outs[4].split('=', 1)[1].split('ms', 1)[0]
                ttl = outs[5].split('=', 1)[1]
                data += '%s,%s,%s' % (byts, delay, ttl)
                seq += 1
            elif out.startswith(miss_str):
                print out
                data = '%d,' % seq
                data += '0,-1,0'
                seq += 1
            else:
                continue
            fi.write(data + '\n')
            fi.flush()
    fi.close()

def upload(logfile):
    fi = open(logfile, 'rb')
    data = fi.read()
    fi.close()
    headers = {"Content-type": "text/plain"}
    srv_url = "http://%s:%d/file/%s" % (processor, processor_port, logfile)
    cli = httplib.HTTPConnection(processor, processor_port, timeout=30)
    cli.request("PUT", srv_url, data, headers)
    res = cli.getresponse()
    if res.status == 200:
        return 0
    return 1

if __name__ == '__main__':
    print 'PALLN test starting...'
    print 'Target is %s' % target

    code = chcp()

    tid = shortuuid.uuid()

    baselog = 'base_%s.log' % tid
    writebase(baselog)
    ret = 1
    count = 0
    while ret != 0:
        count += 1
        if count == 4:
            break
        ret = upload(baselog)
        if ret == 0:
            os.system('del %s' % baselog)

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
