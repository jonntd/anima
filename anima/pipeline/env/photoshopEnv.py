# -*- coding: utf-8 -*-
# Copyright (c) 2012-2013, Anima Istanbul
#
# This module is part of anima-tools and is released under the BSD 2
# License: http://www.opensource.org/licenses/BSD-2-Clause
from _ctypes import COMError

import os
import logging

import comtypes.client
from base import EnvironmentBase


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PhotoshopEnv(EnvironmentBase):
    """The photoshop environment class
    """
    name = "Photoshop"
    extensions = ['.psd']

    def __init__(self):
        """photoshop specific init
        """
        # connect to the application
        self.photoshop = comtypes.client.CreateObject('Photoshop.Application')

    def save_as(self, version):
        """the save action for photoshop environment

        :param version: stalker.models.version.Version instance
        :return:
        """
        from stalker import Version
        if not isinstance(version, Version):
            raise RuntimeError(
                '"version" argument in %s.save_as() should be a'
                'stalker.models.version.Version instance, not %s' % (
                    self.__class__.__name__,
                    version.__class__.__name__
                )
            )

        version.update_paths()
        version.extension = '.psd'
        version.created_with = self.name

        # Define PSD save options
        psd_options = comtypes.client.CreateObject(
            'Photoshop.PhotoshopSaveOptions'
        )
        psd_options.annotations = True
        psd_options.alphaChannels = True
        psd_options.layers = True
        psd_options.spotColors = True
        psd_options.embedColorProfile = True

        #Save PSD
        # create the path before saving
        try:
            os.makedirs(version.absolute_path)
        except OSError:
            # path already exists OSError
            pass

        version_full_path = version.absolute_full_path
        doc = self.photoshop.activeDocument
        doc.SaveAs(
            version_full_path.encode(),
            psd_options
        )
        return True

    def export_as(self, version):
        """export action for photoshop

        :param version: stalker.models.version.Version instance
        :return:
        """
        # TODO: this method uses exactly the same procedure to save the file, so combine them
        from stalker import Version
        if not isinstance(version, Version):
            raise RuntimeError(
                '"version" argument in %s.save_as() should be a'
                'stalker.models.version.Version instance, not %s' % (
                    self.__class__.__name__,
                    version.__class__.__name__
                )
            )

        version.update_paths()
        version.extension = '.psd'
        version.created_with = self.name

        # Define PSD save options
        psd_options = comtypes.client.CreateObject(
            'Photoshop.PhotoshopSaveOptions'
        )
        psd_options.annotations = True
        psd_options.alphaChannels = True
        psd_options.layers = True
        psd_options.spotColors = True
        psd_options.embedColorProfile = True

        #Save PSD
        # create the path before saving
        try:
            os.makedirs(version.absolute_path)
        except OSError:
            # path already exists OSError
            pass

        version_full_path = version.absolute_full_path
        doc = self.photoshop.activeDocument
        doc.ExportAs(
            version_full_path.encode(),
            psd_options
        )
        return True

    def open_(self, version, force=False):
        """open action for photoshop environment

        :param version: stalker.models.version.Version instance
        :param force: force open file
        :return:
        """
        version_full_path = version.absolute_full_path
        version_full_path = version_full_path.replace('/', '\\')
        self.photoshop.Load(version_full_path)

        return True, []

    def post_open(self, version):
        """do nothing

        :param version: stalker.models.version.Version instance
        :return:
        """
        return True

    def get_current_version(self):
        """Finds the Version instance from the current ActiveDocument.

        If it can't find any then returns None.

        :return: :class:`~stalker.models.version.Version`
        """
        version = None

        try:
            doc = self.photoshop.activeDocument
            full_path = doc.FullName
        except COMError:
            # no active document
            return None

        logger.debug('full_path : %s' % full_path)
        # try to get it from the current open scene
        if full_path != '':
            logger.debug("trying to get the version from current file")
            version = self.get_version_from_full_path(full_path)
            logger.debug("version from current file: %s" % version)

        return version

    def get_version_from_recent_files(self):
        """It will try to create a
        :class:`~stalker.models.version.Version` instance by looking at
        the recent files list.

        It will return None if it can not find one.

        :return: :class:`~stalker.models.version.Version`
        """
        version = None

        logger.debug("trying to get the version from recent file list")
        # read the fileName from recent files list
        # try to get the a valid asset file from starting the last recent file

        try:
            recent_files = self.photoshop.RecentFiles
        except KeyError:
            logger.debug("no recent files")
            recent_files = None

        if recent_files is not None:
            for i in range(len(recent_files)-1, -1, -1):
                version = self.get_version_from_full_path(recent_files[i])
                if version is not None:
                    break

            logger.debug("version from recent files is: %s" % version)

        return version
