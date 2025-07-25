import hashlib
import json
import os
import shutil
import tarfile
import tempfile

import urllib2


class UpgradeResult:
    def __init__(self, success, message):
        self.success = success
        self.message = message


class AgentUpgradeManager:
    def __init__(self, logger, agent_dir):
        self.logger = logger
        self.agent_dir = agent_dir

    def upgrade(self, target_version, url, sha256):
        self.logger.info('Starting upgrade to '
                         'version {}'.format(target_version))

        tmp_dir = tempfile.mkdtemp()
        backup_dir = os.path.join(tmp_dir, 'backup')
        package_path = os.path.join(tmp_dir, 'agent_package.tar.gz')
        lockfile_path = os.path.join(self.agent_dir, '.upgrading.lock')

        # Prevent concurrent upgrades
        if os.path.exists(lockfile_path):
            self.logger.warning('Upgrade already in progress. '
                                'Lockfile exists.')
            return UpgradeResult(False, 'Upgrade skipped: '
                                        'already in progress.')

        try:
            # Create a lock file
            with open(lockfile_path, 'w') as f:
                f.write('Upgrade started')

            # Backup current agent dir
            shutil.copytree(self.agent_dir, backup_dir)
            self.logger.info('Backup created at {}'.format(backup_dir))

            # Download the package
            self.logger.info('Downloading package from {}'.format(url))
            response = urllib2.urlopen(url)
            with open(package_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            response.close()

            # Verify SHA256 of downloaded archive
            self.logger.info('Verifying package SHA256')
            sha256_actual = hashlib.sha256()
            with open(package_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256_actual.update(chunk)

            if sha256_actual.hexdigest() != sha256:
                msg = 'SHA256 mismatch: expected {}, got {}'.format(
                    sha256, sha256_actual.hexdigest()
                )
                raise ValueError(msg)

            # Unpack the archive
            self.logger.info('Extracting package')
            with tarfile.open(package_path) as tar:
                tar.extractall(path=tmp_dir)

            extracted_dir = os.path.join(tmp_dir, 'agent')

            # Read manifest.json and verify its fields
            manifest_path = os.path.join(extracted_dir, 'manifest.json')
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                    manifest_version = manifest.get('version')
                    manifest_sha256 = manifest.get('sha256')
                    manifest_files = manifest.get('files', [])

                    # Verify manifest version
                    if manifest_version and manifest_version != target_version:
                        raise ValueError(
                            f'Manifest version {manifest_version} '
                            f'does not match expected target {target_version}'
                        )

                    # Verify manifest sha256 matches the archive
                    if manifest_sha256 and manifest_sha256 != sha256:
                        raise ValueError(
                            f'Manifest SHA256 {manifest_sha256} '
                            f'does not match expected {sha256}'
                        )

                    # Check that all files from manifest exist after extraction
                    missing_files = [
                        f for f in manifest_files
                        if not os.path.exists(os.path.join(extracted_dir, f))
                    ]
                    if missing_files:
                        raise ValueError(f'Missing files after '
                                         f'extraction: {missing_files}')

                    self.logger.info(f'Manifest loaded. '
                                     f'Version: {manifest_version}')

            except Exception as e:
                self.logger.warning('Could not read or verify '
                                    'manifest.json: %s', str(e))
                manifest_version = target_version  # fallback (legacy)

            # Delete old files in agent dir
            for item in os.listdir(self.agent_dir):
                item_path = os.path.join(self.agent_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)

            # Copy new files from extracted package
            for item in os.listdir(extracted_dir):
                src = os.path.join(extracted_dir, item)
                dst = os.path.join(self.agent_dir, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            # Update version.txt
            self.logger.info('Upgrade to {} completed '
                             'successfully'.format(target_version))
            version_file = os.path.join(self.agent_dir, 'version.txt')
            with open(version_file, 'w') as vf:
                vf.write(target_version)

            return UpgradeResult(True, 'Upgrade completed')

        except Exception as e:
            self.logger.exception(f'Upgrade failed with '
                                  f'error: {e}. Restoring from backup.')

            # Rollback to backup
            for item in os.listdir(self.agent_dir):
                item_path = os.path.join(self.agent_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)

            for item in os.listdir(backup_dir):
                src = os.path.join(backup_dir, item)
                dst = os.path.join(self.agent_dir, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            self.logger.info('Rollback completed.')
            return UpgradeResult(False, 'Upgrade failed with exception.')

        finally:
            shutil.rmtree(tmp_dir)
            self.logger.info('Temporary files cleaned up.')

            # Remove the lock file
            if os.path.exists(lockfile_path):
                os.remove(lockfile_path)
                self.logger.info('Lockfile removed.')
