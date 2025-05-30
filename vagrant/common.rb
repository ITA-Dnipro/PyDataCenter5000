module VagrantCommon
  def self.configure_box(config, env)
    config.vm.box = env["OS"]
    config.vm.hostname = env["HOSTNAME"]
    config.vm.synced_folder "agents", "/home/vagrant/agents"
    if env["VM_ARCH"]
      config.vm.box_architecture = env["VM_ARCH"]
    end
    config.vm.provider env["PROVIDER"] do |vb|
      vb.name   = env["VM_NAME"]
      vb.memory = env["VM_MEMORY"]
      vb.cpus   = env["VM_CPUS"]
    end
  end

  def self.base_provision
    <<-SHELL
      set -e
      export DEBIAN_FRONTEND=noninteractive

      apt update
      apt install -y nginx openssh-server

      systemctl enable ssh
      systemctl start ssh

      apt install -y build-essential zlib1g-dev libncurses5-dev libgdbm-dev \
                          libnss3-dev libssl-dev libreadline-dev libffi-dev wget \
                          libsqlite3-dev git

      if ! /opt/python2.6/bin/python2.6 --version > /dev/null 2>&1; then
        cd /usr/src
        wget https://www.python.org/ftp/python/2.6.9/Python-2.6.9.tgz
        tar xzf Python-2.6.9.tgz
        # Instaling zlib
        cd Python-2.6.9/Modules
        cp Setup.dist Setup
        sed -i '/zlibmodule\.c/ s/^# *//' Setup
        cd ..
        ./configure --prefix=/opt/python2.6
        make
        make install
        cd ..
        rm -rf Python-2.6.9 Python-2.6.9.tgz
      fi

      echo "Python 2.6 version:"
      /opt/python2.6/bin/python2.6 --version
      ln -sf /opt/python2.6/bin/python2.6 /usr/local/bin/python2

      # Instaling setuptools
      wget https://bootstrap.pypa.io/ez_setup.py
      python2 ez_setup.py

      # Instaling psutil
      git clone https://github.com/giampaolo/psutil.git
      cd psutil
      git checkout release-5.7.0
      python2 setup.py install
      cd ..

    SHELL
  end
end
