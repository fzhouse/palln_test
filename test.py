#coding=gbk

import subprocess
import time
import shortuuid
import os
import platform
import httplib
import json
import logging

target = '8.8.8.8'
processor = '10.0.63.200'
processor_port = 8001

ping_duration = 10
ping_seg = 300

logger = logging.getLogger('netdiag')
logger.setLevel(logging.DEBUG)
hdr = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)-15s] %(filename)s %(levelname)-4s %(message)s')
hdr.setFormatter(formatter)
logger.addHandler(hdr)

def find_ip_loc():
    try:
        cli = httplib.HTTPConnection('ipinfo.io', 80, timeout=30)
        cli.request('GET', 'http://ipinfo.io')
        res = cli.getresponse()
        data = res.read()
        logger.info(data)
        ipinfo = json.loads(data)
        return ipinfo
    except Exception, e:
        return None

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
    logger.info('Your system language is ' + lang)
    return code

def writebase(logfile):
    fi = open(logfile, 'w+')
    ipinfo = find_ip_loc()
    baseinfo = dict()
    try:
        baseinfo['target'] = target
        baseinfo['platform'] = platform.platform()
        baseinfo['time'] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        baseinfo['ip'] = ipinfo['ip']
        loc = raw_input('Input your location:')
        if loc == '':
            baseinfo['location'] = ipinfo['city'] + ' ' + ipinfo['region'] + ' ' + ipinfo['country']
        else:
            baseinfo['location'] = loc
        org = raw_input('Input your ISP:')
        if org == '':
            baseinfo['org'] = ipinfo['org']
        else:
            baseinfo['org'] = org
    except Exception,e:
        logger.error(e)
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
            logger.debug(out)
            fi.write(data + '\n')
            fi.flush()
    fi.close()

def ping(code, count, offset, logfile):
    cmd = 'ping -n %d %s' % (count, target)
    fi = open(logfile, 'a')
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
    seq = offset+1
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
                logger.debug(out)
                data = '%d,' % seq
                outs = out.split()
                byts = outs[3].split('=', 1)[1]
                delay = outs[4].split('=', 1)[1].split('ms', 1)[0]
                ttl = outs[5].split('=', 1)[1]
                data += '%s,%s,%s' % (byts, delay, ttl)
                seq += 1
            elif out.startswith(miss_str):
                logger.debug(out)
                data = '%d,' % seq
                data += '0,-1,0'
                seq += 1
            else:
                continue
            fi.write(data + '\n')
            fi.flush()
    fi.close()

def upload(logfile):
    logger.info("uploading %s" % logfile)
    fi = open(logfile, 'rb')
    data = fi.read()
    fi.close()
    try:
        headers = {"Content-type": "text/plain"}
        srv_url = "http://%s:%d/file/%s" % (processor, processor_port, logfile)
        cli = httplib.HTTPConnection(processor, processor_port, timeout=10)
        cli.request("PUT", srv_url, data, headers)
        res = cli.getresponse()
        if res.status == 200:
            return 0
        return 1
    except Exception, e:
        logger.error(e)
        return 1

def upload_and_delete(logfile, retry=3):
    ret = 1
    count = 0
    while ret != 0:
        count += 1
        if count == retry+1:
            break
        ret = upload(logfile)
        if ret == 0:
            os.system('del %s' % logfile)

if __name__ == '__main__':
    logger.info('PALLN test starting...')
    logger.info('Target is %s' % target)

    try:
        ping_duration = int(raw_input("Ping duration(minutes):"))
        ping_count = ping_duration * 60
    except Exception,e:
        logger.error(e)

    code = chcp()

    tid = shortuuid.uuid()

    baselog = 'base_%s.log' % tid
    writebase(baselog)
    upload_and_delete(baselog)

    trlog = 'tracert_%s.log' % tid
    traceroute(code, trlog)
    upload_and_delete(trlog)

    pinglog = 'ping_%s.log' % tid
    offset = 0
    while ping_count > 0:
        if ping_count > ping_seg:
            count = ping_seg
        else:
            count = ping_count
        ping(code, count, offset, pinglog)
        ping_count = ping_count - count
        offset = offset + count
        logger.info('finished %d' % offset)
        upload_and_delete(pinglog)
