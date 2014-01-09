import pyrax
from time import sleep

from monster import util
from openstack import Openstack
from monster.clients.openstack import Creds

class Rackspace(Openstack):
    """
    Provisions chef nodes in Rackspace Cloud Servers vms
    """

    def __init__(self):
        rackspace = util.config['secrets']['rackspace']

        self.names = []
        self.name_index = {}
        self.creds = Creds(
            user=rackspace['user'], apikey=rackspace['api_key'],
            auth_url=rackspace['auth_url'], region=rackspace['region'],
            auth_system=rackspace['plugin'], provisioner="rackspace")

        pyrax.set_setting("identity_type", "rackspace")
        pyrax.set_credentials(self.creds.user, api_key=self.creds.apikey,
                              region=self.creds.region)
        pyrax.connect_to_services()

        self.client = pyrax.cloudservers
        self.neutron = pyrax.cloud_networks

    def post_provision(self, node):
        """
        Tasks to be done after a rackspace node is provisioned
        :param node: Node object to be tasked
        :type node: Monster.Node
        """
        self.mkswap(node)
        self.hosts(node)
        if "controller" in node.name and self.deployment.os_name == "centos":
            self.rdo()

    def rdo(self, node):
        kernel = util.config['rcbops']['compute']['kernel']
        version = kernel['centos']['version']
        install = kernel['centos']['install']
        if not node.run_cmd("uname -r")['return'] == version:
            node.run_cmd(install)
            node.run_cmd("reboot now")
            sleep(30)

    def hosts(self, node):
        """
        remove /etc/hosts entries
        rabbitmq uses hostnames and don't listen on the existing public ifaces
        :param node: Node object to clean ifaces
        :type node: Monster.node
        """
        cmd = ("sed '/{0}/d' /etc/hosts > /etc/hosts; "
               "echo '127.0.0.1 localhost' >> /etc/hosts".format(node.name))
        node.run_cmd(cmd)

    def mkswap(self, node, size=2):
        """
        Makes a swap file of size on the node
        :param node: Node to create swap file
        :type node: monster.Node
        :param size: Size of swap file in GBs
        :type size: int
        """
        util.logger.info("Making swap file on:{0} of {1}GBs".format(node.name,
                                                                    size))
        size_b = int(pow(1024, size))
        cmds = [
            "dd if=/dev/zero of=/mnt/swap bs=1024 count={0}".format(size_b),
            "mkswap /mnt/swap",
            "sed 's/vm.swappiness.*$/vm.swappiness=25/g' "
            "/etc/sysctl.conf > /etc/sysctl.conf",
            "sysctl vm.swappiness=30",
            "swapon /mnt/swap"
        ]
        node.run_cmd("; ".join(cmds))