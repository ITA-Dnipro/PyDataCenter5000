import hashlib
import json
import os
import shutil
import tarfile
import tempfile

import urllib2

from .upgrade_utils import (BackupCreationError, DownloadError,
                            ExtractionError, Sha256MismatchError,
                            create_backup, download_file, extract_tarball,
                            verify_sha256)


# Update status codes
class UpgradeStatus:
    SUCCESS = 0
    FAILED = 1
    SKIPPED = 2


class UpgradeResult:
    def __init__(self, status, message):
        self.status = status
        self.message = message

    def is_success(self):
        return self.status == UpgradeStatus.SUCCESS

    def is_failed(self):
        return self.status == UpgradeStatus.FAILED

    def is_skipped(self):
        return self.status == UpgradeStatus.SKIPPED


class AgentUpgradeManager(object):
    def __init__(self, logger, agent_dir):
        self.logger = logger
        self.agent_dir = agent_dir

    def upgrade(self, *args, **kwargs):
        raise NotImplementedError('This method should be '
                                  'implemented in subclasses')


class TarballUpgradeManager(AgentUpgradeManager):
    def upgrade(self, target_version, url, sha256, *args, **kwargs):
        self.logger.info('Starting upgrade to version %s' % target_version)

        tmp_dir = tempfile.mkdtemp()
        backup_dir = os.path.join(tmp_dir, 'backup')
        package_path = os.path.join(tmp_dir, 'agent_package.tar.gz')
        lockfile_path = os.path.join(self.agent_dir, '.upgrading.lock')

        if os.path.exists(lockfile_path):
            self.logger.warning('Upgrade already in progress. '
                                'Lockfile exists.')
            return UpgradeResult(UpgradeStatus.SKIPPED, 'Upgrade skipped: '
                                                        'already in progress.')

        try:
            with open(lockfile_path, 'w') as f:
                f.write('Upgrade started')

            create_backup(self.agent_dir, backup_dir, self.logger)
            download_file(url, package_path, self.logger)
            verify_sha256(package_path, sha256, self.logger)
            extract_tarball(package_path, tmp_dir, self.logger)

            #  Validation of manifest.json
            manifest_path = os.path.join(tmp_dir, 'manifest.json')
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                    manifest_version = manifest.get('version')
                    manifest_sha256 = manifest.get('sha256')
                    manifest_files = manifest.get('files', [])

                    # Version check
                    if manifest_version and manifest_version != target_version:
                        raise ValueError(
                            f"Manifest version '{manifest_version}' does not "
                            f"match expected '{target_version}'"
                        )
                    # SHA256 verification
                    if manifest_sha256 and manifest_sha256 != sha256:
                        raise ValueError(
                            f"Manifest sha256 '{manifest_sha256}' "
                            f"does not match expected '{sha256}'"
                        )
                    # File existence check
                    missing_files = [
                        fn for fn in manifest_files
                        if not os.path.exists(os.path.join(tmp_dir, fn))
                    ]
                    if missing_files:
                        raise ValueError(f'Missing files '
                                         f'after extraction: {missing_files}')

                self.logger.info(f'Manifest.json validated. '
                                 f'Version: {manifest_version}')

            except Exception as e:
                self.logger.error(f'Manifest.json validation failed: {e}')
                return UpgradeResult(UpgradeStatus.FAILED,
                                     f'Manifest.json validation failed: {e}')

            extracted_dir = os.path.join(tmp_dir, 'agent')

            # Delete old files
            for item in os.listdir(self.agent_dir):
                item_path = os.path.join(self.agent_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)

            # Copy new files
            for item in os.listdir(extracted_dir):
                src = os.path.join(extracted_dir, item)
                dst = os.path.join(self.agent_dir, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            version_file = os.path.join(self.agent_dir, 'version.txt')
            with open(version_file, 'w') as vf:
                vf.write(target_version)

            return UpgradeResult(UpgradeStatus.SUCCESS, 'Upgrade completed')

        except BackupCreationError as e:
            self.logger.error('Backup creation failed: %s' % e)
            return UpgradeResult(UpgradeStatus.FAILED,
                                 'Upgrade failed: could not create backup')
        except DownloadError as e:
            self.logger.error('Download failed: %s' % e)
            return UpgradeResult(UpgradeStatus.FAILED,
                                 'Upgrade failed: could not download package')
        except Sha256MismatchError as e:
            self.logger.error('SHA256 verification failed: %s' % e)
            return UpgradeResult(UpgradeStatus.FAILED,
                                 'Upgrade failed: sha256 mismatch')
        except ExtractionError as e:
            self.logger.error('Extraction failed: %s' % e)
            return UpgradeResult(UpgradeStatus.FAILED,
                                 'Upgrade failed: could not extract tarball')
        except Exception as e:
            self.logger.exception('Upgrade failed with error:'
                                  ' %s. Restoring from backup.' % e)
            # Rollback
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
            return UpgradeResult(UpgradeStatus.FAILED,
                                 'Upgrade failed with exception: %s' % e)
        finally:
            shutil.rmtree(tmp_dir)
            self.logger.info('Temporary files cleaned up.')
            if os.path.exists(lockfile_path):
                os.remove(lockfile_path)
                self.logger.info('Lockfile removed.')
