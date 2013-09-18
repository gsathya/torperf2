# Copyright (c) 2013, Sathyanarayanan Gunasekaran, The Tor Project, Inc.
# See LICENSE for licensing information

# -*- mode: ruby -*-
# vi: set ft=ruby :

$script = <<SCRIPT
cd /torperf/

./contrib/setup-dependencies.sh -y

# Kill tor if it's running
service tor stop

if [ "$?" = "0" ]; then
  echo "All set! To start the server:"
  echo "'vagrant ssh'"
  echo "'cd /torperf/'"
  echo "'python torperf/torperf.py'"
else
  echo "Looks like we had some setup errors. Please log a bug here: https://github.com/gsathya/torperf2/issues Thanks!" 1>&2;
fi

SCRIPT

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  # All Vagrant configuration is done here. The most common configuration
  # options are documented and commented below. For a complete reference,
  # please see the online documentation at vagrantup.com.

  # Every Vagrant virtual environment requires a box to build off of.
  config.vm.box = "precise32"
  config.vm.network :forwarded_port, guest: 8888, host: 8888

  # The url from where the 'config.vm.box' box will be fetched if it
  # doesn't already exist on the user's system.
  config.vm.box_url = "http://files.vagrantup.com/precise32.box"

  # Share an additional folder to the guest VM. The first argument is
  # the path on the host to the actual folder. The second argument is
  # the path on the guest to mount the folder. And the optional third
  # argument is a set of non-required options.
  config.vm.synced_folder ".", "/torperf"

  config.vm.provision :shell, :inline => $script
end
