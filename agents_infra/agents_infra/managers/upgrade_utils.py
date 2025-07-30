import hashlib
import os
import shutil
import tarfile

import urllib2


class BackupCreationError(Exception):
    pass


class DownloadError(Exception):
    pass


class Sha256MismatchError(Exception):
    pass


class ExtractionError(Exception):
    pass


def create_backup(src_dir, backup_dir, logger=None):
    try:
        shutil.copytree(src_dir, backup_dir)
        if logger:
            logger.info('Backup created at %s' % backup_dir)
    except Exception as e:
        if logger:
            logger.error('Failed to create backup: %s' % e)
        raise BackupCreationError(e)


def download_file(url, dest_path, logger=None):
    try:
        response = urllib2.urlopen(url)
        with open(dest_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        response.close()
        if logger:
            logger.info('Downloaded package from %s' % url)
    except Exception as e:
        if logger:
            logger.error('Failed to download file: %s' % e)
        raise DownloadError(e)


def verify_sha256(file_path, expected_sha256, logger=None):
    sha256_actual = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256_actual.update(chunk)
        actual = sha256_actual.hexdigest()
        if actual != expected_sha256:
            msg = (
                'SHA256 mismatch: expected %s, got %s'
                % (expected_sha256, actual)
            )
            if logger:
                logger.error(msg)
            raise Sha256MismatchError(msg)
        if logger:
            logger.info('SHA256 verified')
    except Exception as e:
        if logger:
            logger.error('SHA256 verification failed: %s' % e)
        raise


def extract_tarball(tar_path, extract_to, logger=None):
    try:
        with tarfile.open(tar_path) as tar:
            tar.extractall(path=extract_to)
        if logger:
            logger.info('Extracted package to %s' % extract_to)
    except Exception as e:
        if logger:
            logger.error('Failed to extract tarball: %s' % e)
        raise ExtractionError(e)
