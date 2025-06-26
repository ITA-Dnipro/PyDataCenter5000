module VagrantCommon
  def self.configure_box(config, env)
    config.vm.box = env["OS"]
    config.vm.hostname = env["HOSTNAME"]
    config.vm.synced_folder "agents_infra/agents_infra", "/home/vagrant/agents_infra"
    config.vm.synced_folder "agents_infra/scripts", "/home/vagrant/scripts"
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
      cd /home/vagrant/scripts
      chmod +x setup-server.sh install-dependencies.sh
      bash setup-server.sh && bash install-dependencies.sh
      cp /home/vagrant/agents_infra/.coveragerc /home/vagrant/.coveragerc
    SHELL
  end
end
