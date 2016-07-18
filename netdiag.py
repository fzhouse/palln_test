import platform
import logging
import shortuuid
import json
import subprocess
import paramiko
import getpass


logger = logging.getLogger('netdiag')
logger.setLevel(logging.DEBUG)
hdr = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)-15s] %(filename)s %(levelname)-8s %(message)s')
hdr.setFormatter(formatter)
logger.addHandler(hdr)

class Node():
    def __init__(self, address, name=None):
        self.address = address
        if name:
            self.name = name
        self.name = address

class Host(Node):
    def __init__(self, address, name=None, ssh_address=None, ssh_port=22, username='root', password=None, keyfile=None):
        Node.__init__(self, address, name)
        if self.address == '127.0.0.1':
            username = self.getpass.getuser()
        if ssh_address:
            self.ssh_address = ssh_address
        else:
            self.ssh_address = address
        self.ssh_port = ssh_port
        self.username = username
        self.password = password
        self.keyfile = keyfile
        self.ssh = None

    def connect(self):
        if self.address == '127.0.0.1':
            return
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
        if self.keyfile:
            logger.info("login with key %s" % self.keyfile)
            ssh.connect(self.ssh_address, port=self.ssh_port, username=self.username, key_filename=self.keyfile)
        elif self.password:
            logger.info("login with password %s" % self.password)
            ssh.connect(self.ssh_address, port=self.ssh_port, username=self.username, password=self.password)
        else:
            ssh.connect(self.ssh_address, port=self.ssh_port, username=self.username, key_filename='%s/.ssh/id_rsa' % os.environ['HOME'])
        self.ssh = ssh
        except Exception, e:
            logger.error("connect error: %s" % e)

    def disconnect(self):
        if self.address == '127.0.0.1':
            return
        self.ssh.close()

    def exec_command(self, cmd):
        if self.address == '127.0.0.1':
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
            stdout, stderr = p.communicate()
            return stdout
        try:
            logger.info('[%s@%s] %s' % (self.username, self.address, cmd))
            stdin, stdout, stderr = self.ssh.exec_command(cmd)
            out = stdout.readlines()
            return out
        except Exception, e:
            logger.error(e)

    def make_scripts(self, cmds):
        logger.info(cmds)
        cmds.append("rm -- \"$0\"")
        br = '\n'
        cmd = br.join(cmds)
        fi = open("./run.sh", "w")
        fi.write(cmd)
        fi.close()
        self.put_file("./run.sh", "/tmp/run.sh")
        os.system("rm -rf ./run.sh")

    def exec_commands(self, cmds):
        self.make_scripts(cmds)
        return self.exec_command("/bin/bash /tmp/run.sh")

    def exec_command_bg(self, cmd, log):
        cmds = ["nohup %s &> /tmp/%s &" % (cmd, log), "echo $!"]
        pid = int(self.exec_commands(cmds)[0], 10)
        logger.info("%s pid: %s" % (cmd, pid))
        return pid

    def exec_commands_bg(self, cmds, log):
        self.make_scripts(cmds)
        self.exec_command_bg("/bin/bash /tmp/run.sh", log)

    def kill_pid(self, pid):
        self.exec_command("kill -2 %d" % pid)

    def get_file(self, remotepath, localdir="."):
        filename = os.path.basename(remotepath)
        localpath = "%s/%s_%s" % (localdir, self.address, filename)
        if self.address == '127.0.0.1':
            p = subprocess.Popen('cp %s %s' % (remotepath, localpath))
            p.wait()
            logger.info("[%s@%s] put %s to %s" % (self.username, self.address, localpath, remotepath))
            return
        try:
            sftp = self.ssh.open_sftp()
            sftp.get(remotepath, localpath)
            sftp.close()
            logger.info("[%s@%s] get %s from %s" % (self.username, self.address, localpath, remotepath))
        except e:
            logger.error(e)

    def put_file(self, localpath, remotepath):
        if self.address == '127.0.0.1':
            p = subprocess.Popen('cp %s %s' % (localpath, remotepath))
            p.wait()
            logger.info("[%s@%s] put %s to %s" % (self.username, self.address, localpath, remotepath))
            return
        try:
            sftp = self.ssh.open_sftp()
            sftp.put(localpath, remotepath)
            logger.info("[%s@%s] put %s to %s" % (self.username, self.address, localpath, remotepath))
        except e:
            logger.error(e)

    def wait_pid(self, pid):
        while 1:
            out = self.exec_command("ps -q %d" % pid)
            if len(out) == 2:
                time.sleep(10)
            else:
                return


class DiagHost(Host):
    def __init__(self, name, address, ssh_address, ssh_port=22, username='root', password='', keyfile=None, iperf_port=5001):
        Host.__init__(self, name, address, ssh_address, ssh_port, username, password, keyfile)
        self.iperf_port = iperf_port

    def run_iperf_server(self, log):
        cmd = "iperf -s -u -i 1 -p %d -y C" % self.iperf_port
        return self.exec_command_bg(cmd, log)

    def run_iperf_client(self, remote, log):
        cmd = "iperf -c %s -u -d -b %s -t %d -i 1 -p %d -y C" % (remote.address, test_bandwidth, test_duration, remote.iperf_port)
        return self.exec_command_bg(cmd, log)

    def run_ping(self, remote, log):
        cmd = "ping -A %s" % remote.address
        return self.exec_command_bg(cmd, log)

    def run_mtr(self, remote, log):
        cmd = "mtr -r -n -C -c %d -i %.1f %s | sed 's/;/,/g'" % (mtr_count, mtr_int, remote.address)
        return self.exec_command_bg(cmd, log)

    def run_sar(self, log):
        cmd = "/usr/lib64/sa/sadc 1 14400"
        return self.exec_command_bg(cmd, log)

    def kill_iperf(self):
        cmd = "killall -2 iperf"
        self.exec_command(cmd)

    def kill_sar(self, log):
        cmds = ["killall -2 sadc", "mv /tmp/%s /tmp/tmplog" % log, "sadf -d /tmp/tmplog -- -r -n DEV | grep -v '^#' | sed 's/;/,/g' > /tmp/%s" % log, "rm -rf /tmp/tmplog"]
        self.exec_commands(cmds)

    def kill_ping(self):
        cmd = "killall -2 ping"
        self.exec_command(cmd)

    def rm_file(self, path):
        cmd = "rm -rf %s" % path
        self.exec_command(cmd)

    def clear_procs(self):
        cmds = ["killall -2 iperf", "killall -2 sadc", "killall -2 ping", "rm -rf /tmp/*.log"]
        self.exec_commands(cmds)

    def clear_logs(self, tid):
        self.exec_command("rm -rf /tmp/*%s.log" % tid)



if __name__ == '__main__':
    h1 = Host(address='10.0.63.202', password='startimes123!@#')
    h1.connect()
    h1.exec_command('hostname')
    print h1.exec_command_bg('sleep 10')
    h1.disconnect()
    # May not work for Windows
    h2 = Host(address='127.0.0.1')
    h2.connect()
    h2.exec_command('hostname')
    h2.exec_command_bg('ping 114.114.114.114')
    h2.disconnect()
