"""
A nodes features
"""
from monster import util
from Feature import Feature, remove_chef
from chef import ChefAPI


class Node(Feature):
    """ Represents a feature on a node
    """

    def __init__(self, node):
        super(Node, self).__init__(node.deployment.config)
        self.node = node

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def pre_configure(self):
        pass

    def apply_feature(self):
        pass

    def post_configure(self):
        pass

    def set_run_list(self):
        """ Sets the nodes run list based on the Feature
        """

        # have to add logic for controllers
        if hasattr(self, "number"):
            # Set the role based on the feature name and number of the node
            role = "{0}{1}".format(self.__class__.__name__.lower(),
                                   self.number)
        else:
            role = self.__class__.__name__.lower()

        # Set the run list based on the deployment config for the role
        run_list = self.config['rcbops'][self.node.product][role]['run_list']

        # Add the run list to the node
        self.node.add_run_list_item(run_list)


class Controller(Node):
    """ Represents a RPCS Controller
    """

    def __init__(self, node):
        super(Controller, self).__init__(node)
        self.number = None

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def pre_configure(self):
        if self.node.deployment.has_controller:
            self.number = 2
            self.set_run_list()
        else:
            self.number = 1
            self.set_run_list()

    def apply_feature(self):
        """
        Run chef client on controler1 after controller2's completes
        """
        self.node.deployment.has_controller = True

        if self.number == 2:
            controllers = self.node.deployment.search_role('controller')
            controller1 = next(controllers)
            controller1.run_cmd('chef-client')


class Compute(Node):
    """ Represents a RPCS compute
    """

    def __init__(self, node):
        super(Compute, self).__init__(node)

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def pre_configure(self):
        self.set_run_list()


class Proxy(Node):
    """ Represents a RPCS proxy node
    """

    def __init__(self, node):
        super(Proxy, self).__init__(node)

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def pre_configure(self):
        self.set_run_list()


class Storage(Node):
    """ Represents a RPCS proxy node
    """

    def __init__(self, node):
        super(Storage, self).__init__(node)

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def pre_configure(self):
        self.set_run_list()


class Remote(Node):
    """ Represents the deployment having a remote chef server
    """

    def __init__(self, node):
        super(Remote, self).__init__(node)

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def apply_feature(self):
        remove_chef(self.node)
        self._bootstrap_chef()

    def _bootstrap_chef(self):
        """ Bootstraps the node to a chef server
        """

        # Gather the info for the chef server
        chef_server_node = self.node.deployment.search_role('chef_server')

        command = 'knife bootstrap {0} -s root -p {1}'.format(
            chef_server_node.ipaddress, self.node.password)

        chef_server_node.run_cmd(command)


class Cinder(Node):
    """
    Enables cinder with local lvm backend
    """

    def __init__(self, node):
        super(Cinder, self).__init__(node)

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def pre_configure(self):
        self.prepare_cinder()
        self.set_run_list()

    def prepare_cinder(self):
        """ Prepares the node for use with cinder
        """

        # Update our environment
        env = self.node.environment
        vol_group = self.config['cinder']['vg_name']
        cinder = {
            "storage": {
                "lvm": {
                    "volume_group": vol_group
                }
            }
        }
        util.logging.info("Setting cinder volume to {0}".format(vol_group))
        env.add_override_attr("cinder", cinder)


class ChefServer(Node):
    """ Represents a chef server
    """

    def __init__(self, node):
        super(ChefServer, self).__init__(node)
        self.iscript = self.config['chef']['server']['install_script']
        self.iscript_name = self.iscript.split('/')[-1]
        self.install_commands = ['curl {0} >> {1}'.format(self.iscript,
                                                          self.iscript_name),
                                 'chmod u+x ~/{0}'.format(self.iscript_name),
                                 './{0}'.format(self.iscript_name)]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def pre_configure(self):
        remove_chef(self.node)

    def apply_feature(self):
        self._install()
        self._install_cookbooks()
        self._set_up_remote()

    def _install(self):
        """ Installs chef server on the given node
        """

        command = "; ".join(self.install_commands)
        self.node.run_cmd(command)

    def _install_cookbooks(self):
        """ Installs cookbooks
        """

        cookbook_url = self.config['rcbops'][self.node.product]['git']['url']
        cookbook_branch = self.node.branch
        cookbook_name = cookbook_url.split("/")[-1].split(".")[0]
        install_dir = self.config['chef']['server']['install_dir']

        commands = ["mkdir -p {0}".format(install_dir),
                    "cd {0}".format(install_dir),
                    "git clone {0}".format(cookbook_url),
                    "cd {0}/chef-cookbooks".format(install_dir),
                    "git checkout {0}".format(cookbook_branch)]

        if 'cookbooks' in cookbook_name:
             # add submodule stuff to list
            commands.append('git submodule init')
            commands.append('git submodule sync')
            commands.append('git submodule update')
            commands.append('knife cookbook upload --all --cookbook-path '
                            '{0}/{1}/cookbooks'.format(install_dir,
                                                       cookbook_name))
        else:
            commands.append('knife cookbook upload --all'
                            ' --cookbook-path {0}/{1}'.format(install_dir,
                                                              cookbook_name))

        commands.append('knife role from file {0}/{1}/roles/*.rb'.format(
            install_dir, cookbook_name))

        command = "; ".join(commands)

        return self.node.run_cmd(command)

    def _set_up_remote(self):
        """ Sets up and saves a remote api and dict to the nodes
            environment
        """

        remote_chef = {
            "client": "admin",
            "key": self._get_admin_pem(),
            "url": "https://{0}:4443".format(self.node.ipaddress)
        }

        # set the remote chef server name
        self.node.environment.chef_server_name = self.node.name

        # save the remote dict
        self.node.environment.add_override_attr('remote_chef', remote_chef)

        # set the remote api
        remote_api = self._remote_chef_api(remote_chef)
        self.node.environment.remote_api = remote_api

    def _remote_chef_api(self, chef_api_dict):
        """ Builds a remote chef API object
        """

        return ChefAPI(**chef_api_dict)

    def _get_admin_pem(self):
        """ Gets the admin pem from the chef server
        """

        command = 'cat ~/.chef/admin.pem'
        return self.node.run_cmd(command)['return']


class OpenLDAP(Node):
    """ Represents a LDAP server
    """

    def __init__(self, node):
        super(OpenLDAP, self).__init__()

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def pre_configure(self):
        self.set_run_list()

    def post_configure(self):
        self._configure_ldap()

    def _configure_ldap(self):
        ldapadd = 'ldapadd -x -D "cn=admin,dc=rcb,dc=me" -wsecrete -f /root/base.ldif'
        self.node.run_cmd(ldapadd)

class Celiometer(Node):
    """ Represents a Celiometer Node
    """

    def __init__(self, node):
        super(Celiometer, self).__init__()
        self.role = None

    def __repr__(self):
        """ Print current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def pre_configure(self):
        if 'controller' in self.node.features:
            self.role = 'controller'
        else:
            self.role = 'compute'

        self._set_run_list()

    def _set_run_list(self):
        """ Celiometer run list set
        """

        role = self.__class__.__name__.lower()

        # Set the run list based on the deployment config for the role
        run_list = self.config['rcbops'][self.node.product]\
                              [role][self.role]['run_list']

        # Add the run list to the node
        self.node.add_run_list_item(run_list)