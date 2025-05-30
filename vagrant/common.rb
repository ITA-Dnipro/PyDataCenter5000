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
    # Importing bash
    <<-SHELL
      chmod +x /vagrant/scripts/common.sh
      /vagrant/scripts/common.sh
    SHELL
  end
end
