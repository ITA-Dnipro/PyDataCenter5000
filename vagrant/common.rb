module VagrantCommon
  def self.configure_box(config, env)
    config.vm.box = env["OS"]
    config.vm.hostname = env["HOSTNAME"]
    config.vm.synced_folder "agents", "/home/vagrant/agents"
    config.vm.provider env["PROVIDER"] do |vb|
      vb.name   = env["VM_NAME"]
      vb.memory = env["VM_MEMORY"]
      vb.cpus   = env["VM_CPUS"]
    end
  end

  def self.base_provision
    <<-SHELL
      set -e

      sudo apt update
      sudo apt install -y nginx openssh-server

      sudo systemctl enable ssh
      sudo systemctl start ssh

      sudo apt install -y build-essential zlib1g-dev libncurses5-dev libgdbm-dev \
                          libnss3-dev libssl-dev libreadline-dev libffi-dev wget \
                          libsqlite3-dev

      if ! /opt/python2.6/bin/python2.6 --version > /dev/null 2>&1; then
        cd /usr/src
        sudo wget https://www.python.org/ftp/python/2.6.9/Python-2.6.9.tgz
        sudo tar xzf Python-2.6.9.tgz
        # Instaling zlib
        cd Python-2.6.9/Modules
        sudo cp Setup.dist Setup
        sudo sed -i '/zlibmodule\.c/ s/^# *//' Setup
        cd ..
        sudo ./configure --prefix=/opt/python2.6
        sudo make
        sudo make install
        cd ..
        sudo rm -rf Python-2.6.9 Python-2.6.9.tgz
      fi

      echo "Python 2.6 version:"
      /opt/python2.6/bin/python2.6 --version
      sudo ln -sf /opt/python2.6/bin/python2.6 /usr/local/bin/python2

      # Instaling setuptools
      wget https://bootstrap.pypa.io/ez_setup.py
      sudo python2 ez_setup.py

      # Instaling psutil
      git clone https://github.com/giampaolo/psutil.git
      cd psutil
      git checkout release-5.7.0
      sudo python2 setup.py install
      cd ..

    SHELL
  end
end
