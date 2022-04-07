﻿# -*- coding: utf-8 -*-

import os
import re
import shutil

import pymel.core as pm
import maya.cmds as mc
import time

from anima import logger
from anima.dcc import empty_reference_resolution
from anima.dcc.base import DCCBase
from anima.dcc.mayaEnv import extension  # register extensions
from anima.exc import PublishError
from anima.representation import Representation
from anima.utils.progress import ProgressManager, ProgressDialogBase

# empty publishers first
from anima.dcc.mayaEnv import publish as publish_scripts  # register publishers

from anima.publish import (
    run_publishers,
    staging,
    PRE_PUBLISHER_TYPE,
    POST_PUBLISHER_TYPE,
)


def get_maya_main_window():
    """Get the main Maya window as a QtGui.QMainWindow instance
    @return: QtGui.QMainWindow instance of the top level Maya windows

    ref: https://stackoverflow.com/questions/22331337/how-to-get-maya-main-window-pointer-using-pyside
    """
    import sys
    from anima.ui.lib import QtWidgets, QtCore
    from maya import OpenMayaUI

    ptr_conv_func = int
    if sys.version_info.major == 2:
        ptr_conv_func = long

    ptr = OpenMayaUI.MQtUtil.mainWindow()
    if ptr is not None:
        from anima.ui.lib import IS_PYSIDE, IS_PYSIDE2, IS_PYQT4, IS_QTPY

        if IS_PYSIDE():
            import shiboken

            return shiboken.wrapInstance(ptr_conv_func(ptr), QtWidgets.QWidget)
        elif IS_PYSIDE2():
            import shiboken2

            return shiboken2.wrapInstance(ptr_conv_func(ptr), QtWidgets.QWidget)
        elif IS_PYQT4():
            import sip

            return sip.wrapinstance(ptr_conv_func(ptr), QtCore.QObject)


class MayaMainProgressBarWrapper(ProgressDialogBase):
    """Wrap main progress bar dialog to be ProgressManager compliant."""

    def __init__(self):
        super(MayaMainProgressBarWrapper, self).__init__()
        self.progress_bar = pm.windows.getMainProgressBar()
        self.progress_bar.beginProgress()

    def set_current_step(self, step):
        """Set the current step.

        Args:
            step (int): The current step value.
        """
        super(MayaMainProgressBarWrapper, self).set_current_step(step)
        self.progress_bar.setProgress(step)
        self.progress_bar.step()

    def set_range(self, min_range=0, max_range=100):
        """Set the minimum and maximum ranges.

        Args:
            min_range (int): The minimum step value, default is 0.
            max_range (int): The maximum step value, default is 100.
        """
        if min_range == max_range:
            max_range = min_range + 1
        super(MayaMainProgressBarWrapper, self).set_range(min_range, max_range)
        self.progress_bar.setMinValue(min_range)
        self.progress_bar.setMaxValue(max_range)

    def set_title(self, title):
        """Set the title.

        Args:
            title (str): The title.
        """
        super(MayaMainProgressBarWrapper, self).set_title(title)
        self.progress_bar.setStatus(title)

    def was_cancelled(self):
        """Check if cancelled.

        Returns:
            bool: True if cancelled, False otherwise.
        """
        return self.progress_bar.getIsCancelled()

    def close(self):
        """Close the dialog."""
        self.progress_bar.endProgress()


class Maya(DCCBase):
    """The maya DCC class

    .. versionadded:: 0.1.7
       Shallow Reference Updates

       With version 0.1.7 all the scene references are updated *shallowly*,
       that is no new versions are going to be created as opposed to
       **Deep Reference Updates**. With **Shallow Reference Update**, all the
       references in current scene is updated in place. So if a new version of
       a Version is present, Maya will update it to that version in the current
       scene without creating new intermediate versions. This makes things much
       simple and easy to manage.

    .. deprecated::
       Deep Reference Updates

       Deep reference updates are deprecated. Use shallow reference updates.

    """

    name = "Maya%s" % pm.versions.shortName()
    representations = ["Base", "GPU", "ASS", "RS"]
    has_publishers = True

    time_to_fps = {
        "sec": 1,
        "2fps": 2,
        "3fps": 3,
        "4fps": 4,
        "5fps": 5,
        "6fps": 6,
        "8fps": 8,
        "10fps": 10,
        "12fps": 12,
        "game": 15,
        "16fps": 16,
        "20fps": 20,
        "film": 24,
        "pal": 25,
        "ntsc": 30,
        "40fps": 40,
        "show": 48,
        "palf": 50,
        "ntscf": 60,
        "75fps": 75,
        "80fps": 80,
        "100fps": 100,
        "120fps": 120,
        "125fps": 125,
        "150fps": 150,
        "200fps": 200,
        "240fps": 240,
        "250fps": 250,
        "300fps": 300,
        "375fps": 375,
        "400fps": 400,
        "500fps": 500,
        "600fps": 600,
        "750fps": 750,
        "millisec": 1000,
        "1200fps": 1200,
        "1500fps": 1500,
        "2000fps": 2000,
        "3000fps": 3000,
        "6000fps": 6000,
    }

    maya_workspace_file_content = """// Auto Generated by Anima
workspace -fr "3dPaintTextures" "Outputs/data/3dPaintTextures";
workspace -fr "ASS Export" "Outputs/ass";
workspace -fr "ASS" "Outputs/ass";
workspace -fr "Alembic" "Outputs/alembic";
workspace -fr "BIF" "Outputs/data";
workspace -fr "CATIAV4_ATF" "Outputs/data";
workspace -fr "CATIAV5_ATF Export" "Outputs/data";
workspace -fr "CATIAV5_ATF" "Outputs/data";
workspace -fr "DAE_FBX export" "Outputs/data";
workspace -fr "DAE_FBX" "Outputs/data";
workspace -fr "FBX export" "Outputs/geo";
workspace -fr "FBX" "Outputs/geo";
workspace -fr "IGES_ATF Export" "Outputs/data";
workspace -fr "IGES_ATF" "Outputs/data";
workspace -fr "INVENTOR_ATF Export" "Outputs/data";
workspace -fr "INVENTOR_ATF" "Outputs/data";
workspace -fr "JT_ATF Export" "Outputs/data";
workspace -fr "JT_ATF" "Outputs/data";
workspace -fr "NX_ATF Export" "Outputs/data";
workspace -fr "NX_ATF" "Outputs/data";
workspace -fr "OBJ" "Outputs/geo";
workspace -fr "OBJexport" "Outputs/geo";
workspace -fr "PROE_ATF" "Outputs/data";
workspace -fr "SAT_ATF Export" "Outputs/data";
workspace -fr "SAT_ATF" "Outputs/data";
workspace -fr "STEP_ATF Export" "Outputs/data";
workspace -fr "STEP_ATF" "Outputs/data";
workspace -fr "STL_ATF Export" "Outputs/data";
workspace -fr "STL_ATF" "Outputs/data";
workspace -fr "WIRE_ATF Export" "Outputs/data";
workspace -fr "WIRE_ATF" "Outputs/data";
workspace -fr "alembicCache" "Outputs/alembic";
workspace -fr "audio" "Outputs/data";
workspace -fr "autoSave" "autosave";
workspace -fr "bifrostCache" "Outputs/geo/cache";
workspace -fr "clips" "Outputs/data";
workspace -fr "depth" "Outputs/data/renderData/depth";
workspace -fr "diskCache" "Outputs/geo/cache";
workspace -fr "eps" "Outputs/data";
workspace -fr "fileCache" "Outputs/alembic";
workspace -fr "fluidCache" "Outputs/cache/fluid";
workspace -fr "furAttrMap" "Outputs/data/renderData/fur/furAttrMap";
workspace -fr "furEqualMap" "Outputs/data/renderData/fur/furEqualMap";
workspace -fr "furFiles" "Outputs/data/renderData/fur/furFiles";
workspace -fr "furImages" "Outputs/data/renderData/fur/furImages";
workspace -fr "furShadowMap" "Outputs/data/renderData/fur/furShadowMap";
workspace -fr "illustrator" "Outputs/data";
workspace -fr "images" "Outputs";
workspace -fr "iprImages" "Outputs/data/renderData/iprImages";
workspace -fr "mayaAscii" "";
workspace -fr "mayaBinary" "";
workspace -fr "mel" "Outputs/data";
workspace -fr "move" "Outputs/data";
workspace -fr "movie" "Outputs/data";
workspace -fr "offlineEdit" "Outputs/data";
workspace -fr "particles" "Outputs/particles";
workspace -fr "renderData" "Outputs/data";
workspace -fr "scene" "";
workspace -fr "sceneAssembly" "";
workspace -fr "scripts" "Outputs/data";
workspace -fr "shaders" "Outputs/data/renderData/shaders";
workspace -fr "sound" "Outputs/data";
workspace -fr "sourceImages" "Outputs/data";
workspace -fr "teClipExports" "Outputs/data";
workspace -fr "templates" "Outputs/data";
workspace -fr "timeEditor" "Outputs/data";
workspace -fr "translatorData" "Outputs/data";
"""

    executable = {"windows": "maya", "linux": "maya", "osx": "maya"}

    extensions = [".ma", ".mb"]

    def __init__(self, version=None):
        # super(Maya, self).__init__(self.name, version)
        DCCBase.__init__(self, self.name, version)

        self._use_progress_window = None
        if not pm.general.about(batch=1):
            self.use_progress_window = True
        else:
            self.use_progress_window = False

        self.set_arnold_texture_search_path()

    @property
    def use_progress_window(self):
        """Return use progress window state."""
        return self._use_progress_window

    @use_progress_window.setter
    def use_progress_window(self, use_progress_window):
        """Set use_progress_window attribute."""
        self._use_progress_window = use_progress_window
        pdm = ProgressManager()
        if not self._use_progress_window:
            # disable progress window
            pdm.dialog_class = ProgressDialogBase
        else:
            pdm.dialog_class = MayaMainProgressBarWrapper
        pdm.end_progress()  # reset pdm.dialog

    @classmethod
    def set_arnold_texture_search_path(cls):
        """sets environment defaults"""
        start = time.time()
        from stalker import Repository

        all_repos = Repository.query.all()

        try:
            # add all repo paths to Arnold Texture search path
            texture_search_path = []
            for repo in all_repos:
                texture_search_path.append(repo.windows_path)
                texture_search_path.append(repo.linux_path)

            texture_search_path = ";".join(texture_search_path)

            dARO = pm.PyNode("defaultArnoldRenderOptions")
            dARO.setAttr("texture_searchpath", texture_search_path)
        except (pm.MayaNodeError, ValueError, pm.MayaAttributeError):
            pass

        end = time.time()
        logger.debug(
            "set_arnold_texture_search_path() took " "%f seconds" % (end - start)
        )

    def save_as(self, version, run_pre_publishers=True):
        """The save_as action for maya dccDCC.

        It saves the given ``Version`` instance to the Version.absolute_full_path.
        """
        # clean malware
        self.clean_malware()

        start = time.time()
        if version.is_published:
            if run_pre_publishers:
                # before doing anything run all publishers
                type_name = ""
                if version.task.type:
                    type_name = version.task.type.name

                # before running use the staging area to store the current
                # version
                staging["version"] = version
                try:
                    run_publishers(type_name, publisher_type=PRE_PUBLISHER_TYPE)
                except (PublishError, RuntimeError) as e:
                    # do not forget to clean up the staging area
                    staging.clear()

                    # pop up a message box with the error
                    pm.confirmDialog(
                        title="PublishError",
                        icon="critical",
                        message="<b>%s</b><br/><br/>%s" % ("PRE PUBLISH FAILED!!!", e),
                        button=["Ok"],
                    )
                    raise e
        else:
            # run some of the publishers
            publish_scripts.check_node_names_with_bad_characters()

        # get the current version, and store it as the parent of the new
        # version
        current_version = self.get_current_version()

        version.update_paths()

        # set version extension to ma
        version.extension = self.extensions[0]

        # do not save if there are local files
        self.check_external_files(version)

        # define that this version is created with Maya
        version.created_with = self.name

        project = version.task.project

        current_workspace_path = pm.workspace.path

        # create a workspace file inside the same folder of the current version
        workspace_path = version.absolute_path

        # if the new workspace path is not matching the with the previous one
        # update the external paths to absolute version
        logger.debug("current workspace: %s" % current_workspace_path)
        logger.debug("next workspace: %s" % workspace_path)

        if current_workspace_path != workspace_path:
            logger.warning("changing workspace detected!")
            logger.warning(
                "converting paths to absolute, to be able to " "preserve external paths"
            )

            # replace external paths with absolute ones
            self.replace_external_paths()

        # create the workspace folders
        self.create_workspace_file(workspace_path)

        # this sets the project
        pm.workspace.open(workspace_path)

        # create workspace folders
        self.create_workspace_folders(workspace_path)

        # set linear and angular units
        pm.currentUnit(l="cm", a="deg")

        # check if this is a shot related task
        shot = self.get_shot(version)

        # set the render range if it is the first version
        if shot and version.version_number == 1:
            self.set_frame_range(shot.cut_in, shot.cut_out)

        fps = shot.fps if shot else project.fps
        imf = shot.image_format if shot else project.image_format

        self.set_render_resolution(imf.width, imf.height, imf.pixel_aspect)

        # now always setting the scene fps
        self.set_fps(fps)

        # set arnold texture search paths
        self.set_arnold_texture_search_path()

        # set the render file name and version
        self.set_render_filename(version)

        # set sequence manager related data
        self.set_sequence_manager_data(version)

        # set the playblast file name
        self.set_playblast_file_name(version)

        # create the folder if it doesn't exists
        try:
            os.makedirs(version.absolute_path)
        except OSError:
            # already exists
            pass

        # delete the unknown nodes
        unknown_nodes = mc.ls(type="unknown")
        # unlock each possible locked unknown nodes
        for node in unknown_nodes:
            try:
                mc.lockNode(node, lock=False)
            except TypeError:
                pass

        if unknown_nodes:
            mc.delete(unknown_nodes)

        # set the file paths for external resources
        self.replace_external_paths()

        # go to master layer for Maya 2017
        # to prevent __untitled__ collection creation
        from anima.dcc.mayaEnv import auxiliary

        current_render_layer = auxiliary.get_current_render_layer()
        if int(pm.about(v=1)) >= 2017:
            auxiliary.switch_to_default_render_layer()

        # before saving
        # fix modelPanel scriptJob errors
        self.remove_rogue_model_panel_change_events()

        # save the file
        pm.saveAs(version.absolute_full_path, type="mayaAscii")

        # switch back to the last layer
        if int(pm.about(v=1)) >= 2017:
            current_render_layer.setCurrent()

        # update the parent info
        if version != current_version:  # prevent CircularDependencyError
            version.parent = current_version

        # update the reference list
        # IMPORTANT: without this, the update workflow is not able to do
        # updates correctly, so do not disable this
        from stalker.db.session import DBSession

        DBSession.add(version)

        self.update_version_inputs()

        # append it to the recent file list
        self.append_to_recent_files(version.absolute_full_path)

        DBSession.commit()

        # create a local copy
        self.create_local_copy(version)

        # run post publishers here
        if version.is_published:
            from anima.ui.lib import QtCore, QtWidgets, QtGui

            # before doing anything run all publishers
            type_name = ""
            if version.task.type:
                type_name = version.task.type.name

            # show dialog during post publish progress and lock maya
            from anima.ui.utils import initialize_post_publish_dialog

            d = initialize_post_publish_dialog()
            d.show()

            # before running use the staging area to store the current version
            staging["version"] = version
            try:
                run_publishers(type_name, publisher_type=POST_PUBLISHER_TYPE)
                d.close()
            except (PublishError, RuntimeError) as e:
                d.close()
                # do not forget to clean up the staging area
                staging.clear()
                # pop up a message box with the error
                pm.confirmDialog(
                    title="PublishError",
                    icon="critical",
                    message="<b>%s</b><br/><br/>%s" % ("POST PUBLISH FAILED!!!", e),
                    button=["Ok"],
                )
                raise e
            # close dialog in any case
            d.close()

        end = time.time()
        logger.debug("save_as took %f seconds" % (end - start))
        return True

    def export_as(self, version):
        """the export action for maya DCC"""
        # check if there is something selected
        if len(pm.ls(sl=True)) < 1:
            raise RuntimeError("There is nothing selected to export")

        # check if this is the first version
        if version.is_published and not self.allow_publish_on_export:
            # it is not allowed to publish the first version
            raise RuntimeError(
                "It is forbidden to export a published version!!!"
                "<br><br>"
                "Export normally, open version and Publish... "
            )

        # do not save if there are local files
        self.check_external_files(version)

        # set the extension to ma by default
        version.update_paths()
        version.extension = self.extensions[0]
        version.created_with = self.name

        # create the folder if it doesn't exists
        try:
            os.makedirs(version.absolute_path)
        except OSError:
            # already exists
            pass

        # workspace_path = os.path.dirname(version.absolute_path)
        workspace_path = version.absolute_path

        self.create_workspace_file(workspace_path)
        self.create_workspace_folders(workspace_path)

        # export the file
        pm.exportSelected(
            version.absolute_full_path, preserveReferences=1, type="mayaAscii"
        )

        # save the version to database
        from stalker.db.session import DBSession

        DBSession.add(version)
        DBSession.commit()

        # create a local copy
        self.create_local_copy(version)

        return True

    def open(
        self,
        version,
        force=False,
        representation=None,
        reference_depth=0,
        skip_update_check=False,
        prompt=True,
    ):
        """The open action for Maya DCC.

        Opens the given Version file, sets the workspace etc.

        Returns a tuple of Bool and a Dictionary. The Bool value shows if
        everything went alright and the scene is opened without any problem.
        The Dictionary is called the Reference Resolution Dictionary, and has
        three keys ['leave', 'update', 'create'] and each of the keys is
        related with a list of Version instances. These Version instances are
        gathered from all the references in the opened scene no matter how
        deeply they've been referenced. So passing this dictionary to

        :param version: The Stalker Version instance to open.
        :meth:`.update_versions` will update or create new versions as
        necessary. You can also modify this dictionary before passing it to
        :meth:`.update_versions`, so only desired version instances are updated
        or a new version is created for them.

        :param bool force: Force open the file.
        :param representation: Opens the given version with the given
          representations.
        :param int reference_depth: An integer parameter for defining the
         preferred reference depth to be loaded. Should be one of 0, 1, 2, 3
         mapping the values of:

          0: saved state
          1: all
          2: topOnly
          3: none

        :param bool skip_update_check: Skip update check if True.

        :param bool prompt: prompts for missing references

        :returns: (Bool, Dictionary)
        """
        reference_depth_res = [None, "all", "topOnly", "none"]

        # store current workspace path
        previous_workspace_path = pm.workspace.path

        # set the project
        # new_workspace = os.path.dirname(version.absolute_path)
        new_workspace = version.absolute_path

        pm.workspace.open(new_workspace)

        # check for unsaved changes
        logger.info("opening file: %s" % version.absolute_full_path)

        self.set_playblast_file_name(version)
        try:
            # switch representations
            if representation and representation != Representation.base_repr_name:
                logger.info("requested representation: %s" % representation)
                # so we have a representation request
                pm.openFile(
                    version.absolute_full_path,
                    f=force,
                    loadReferenceDepth="none",
                    prompt=prompt,
                    ignoreVersion=True,
                )
                # list all references and switch their paths
                for ref in pm.listReferences():
                    logger.debug("switching: %s" % ref.path)
                    ref.to_repr(representation)
                    # force load reference
                    ref.load()
            else:
                if reference_depth_res[reference_depth] is None:
                    logger.info("not using loadReferenceDepth parameter")
                    # load in saved state
                    pm.openFile(
                        version.absolute_full_path,
                        f=force,
                        prompt=prompt,
                        ignoreVersion=True,
                    )
                else:
                    logger.info(
                        "using loadReferenceDepth:%s"
                        % reference_depth_res[reference_depth]
                    )
                    pm.openFile(
                        version.absolute_full_path,
                        f=force,
                        prompt=prompt,
                        loadReferenceDepth=reference_depth_res[reference_depth],
                        ignoreVersion=True,
                    )
        except RuntimeError as e:
            # restore the previous workspace
            # disabled the following because it was causing the the workspace
            # to revert back to the previous one even when the document has
            # opened successfully
            # pm.workspace.open(previous_workspace_path)

            # raise the RuntimeError again
            # for the interface
            raise e

        # set linear and angular units
        pm.currentUnit(l="cm", a="deg")

        # set the playblast folder

        # set sequence manager related data
        self.set_sequence_manager_data(version)

        self.append_to_recent_files(version.absolute_full_path)

        # replace_external_paths
        self.replace_external_paths()

        # set arnold texture search paths
        self.set_arnold_texture_search_path()

        # after opening the file
        # fix modelPanel scriptJob errors
        self.remove_rogue_model_panel_change_events()
        self.clean_malware()

        if not skip_update_check:
            # check the referenced versions for any possible updates
            return self.check_referenced_versions()
        else:
            return empty_reference_resolution()

    def import_(self, version, use_namespace=True):
        """Imports the content of the given Version instance to the current
        scene.

        :param version: The desired
          :class:`~stalker.models.version.Version` to be imported
        :param bool use_namespace: use namespace or not. Default is True.
        """
        if use_namespace:
            namespace = os.path.basename(version.filename)
            pm.importFile(version.absolute_full_path, namespace=namespace)
        else:
            pm.importFile(version.absolute_full_path, defaultNamespace=True)

        # clean malware
        self.clean_malware()

        return True

    def reference(self, version, use_namespace=True):
        """References the given Version instance to the current Maya scene.

        :param version: The desired
          :class:`~stalker.models.version.Version` instance to be
          referenced.
        :param bool use_namespace: Use namespaces for the referenced versions.
        :return: :class:`~pm.system.FileReference`
        """

        # do not reference anything if this scene is not saved yet
        if pm.sceneName() == "":
            raise RuntimeError("Please save your scene first!!!")

        # use the file name without extension as the namespace
        namespace = os.path.basename(version.nice_name)

        # do not use representation part of the filename
        namespace = namespace.split(Representation.repr_separator)[0]

        if use_namespace:
            ref = pm.createReference(
                version.full_path, gl=True, namespace=namespace, options="v=0"
            )
        else:
            ref = pm.createReference(
                version.full_path,
                gl=True,
                defaultNamespace=True,  # this is not "no namespace", but safe
                options="v=0",
            )

        # replace external paths
        self.replace_external_paths()

        # set the reference state to loaded
        if not ref.isLoaded():
            ref.load()

        # append the referenced version to the current versions references
        # attribute
        current_version = self.get_current_version()
        if current_version:
            current_version.inputs.append(version)
            from stalker.db.session import DBSession

            DBSession.commit()

        # also update version.inputs for the referenced input
        self.update_version_inputs(ref)

        # append it to reference path
        self.append_to_recent_files(version.absolute_full_path)

        return ref

    def get_version_from_workspace(self):
        """Tries to find a version from the current workspace path"""
        logger.debug("trying to get the version from workspace")

        # get the workspace path
        workspace_path = pm.workspace.path
        logger.debug("workspace_path: %s" % workspace_path)

        versions = self.get_versions_from_path(workspace_path)
        version = None

        if len(versions):
            version = versions[0]

        logger.debug("version from workspace is: %s" % version)
        return version

    def get_current_version(self):
        """Finds the Version instance from the current Maya session.

        If it can't find any then returns None.

        :return: :class:`~stalker.models.version.Version`
        """
        version = None

        # pm.env.sceneName() always uses "/"
        full_path = pm.sceneName()
        logger.debug("full_path : %s" % full_path)
        # try to get it from the current open scene
        if full_path != "":
            logger.debug("trying to get the version from current file")
            version = self.get_version_from_full_path(full_path)
            logger.debug("version from current file: %s" % version)

        return version

    def get_last_version(self):
        """Returns the last opened or the current Version instance from the DCC.

        * It first looks at the current open file full path and tries to match
          it with a Version instance.
        * Then searches for the recent files list.
        * Still not able to find any Version instances, will return the version
          instance with the highest id which has the current workspace path in
          its path
        * Still not able to find any Version instances returns None

        :returns: :class:`~stalker.models.version.Version` instance or
            None
        """
        version = self.get_current_version()

        # read the recent file list
        if version is None:
            version = self.get_version_from_recent_files()

        # get the latest possible Version instance by using the workspace path
        if version is None:
            version = self.get_version_from_workspace()

        return version

    def set_sequence_manager_data(self, version):
        """sets the sequenceManager1 node attributes including the version
        number.

        :param version: :class:`~stalker.models.version.Version`
        """
        start = time.time()
        sm = pm.ls("sequenceManager1")[0]
        if sm is not None:
            sm.get_shot_name_template()
            sm.set_task_name(version.task.name)
            sm.set_take_name(version.take_name)
            sm.set_version("v%03d" % version.version_number)

            for seq in sm.sequences.get():
                seq.get_sequence_name()
        end = time.time()
        logger.debug("set_sequence_manager_data() took " "%f seconds" % (end - start))

    def set_render_filename(self, version):
        """sets the render file name"""
        render_output_folder = os.path.join(
            version.absolute_path, "Outputs", "renders"
        ).replace("\\", "/")

        # image folder from the workspace.mel
        try:
            image_folder_from_ws = pm.workspace.fileRules["images"]
        except KeyError:
            # there is a problem with the workspace file
            # just skip this step for now
            image_folder_from_ws = "images"

        image_folder_from_ws_full_path = os.path.join(
            version.absolute_path, image_folder_from_ws
        ).replace("\\", "/")

        version_sig_name = self.get_significant_name(
            version, include_project_code=False
        )

        # check the current renderer
        dRG = pm.PyNode("defaultRenderGlobals")
        current_renderer = dRG.currentRenderer.get()
        if current_renderer == "redshift":
            # do not use <RenderPass> in Redshift
            output_filename_template = (
                "%(render_output_folder)s/<RenderLayer>/"
                "%(version_sig_name)s_<RenderLayer>"
            )
        else:
            output_filename_template = (
                "%(render_output_folder)s/<RenderLayer>/"
                "%(version_sig_name)s_<RenderLayer>_<RenderPass>"
            )

        render_file_full_path = output_filename_template % {
            "render_output_folder": render_output_folder,
            "version_sig_name": version_sig_name,
        }

        # convert the render_file_full_path to a relative path to the
        # imageFolderFromWS_full_path
        from anima import utils

        render_file_rel_path = utils.relpath(
            image_folder_from_ws_full_path, render_file_full_path, sep="/"
        )

        if self.has_stereo_camera():
            # just add the <Camera> template variable to the file name
            render_file_rel_path += "_<Camera>"

        # TODO: Some of the following code is repeated in self.set_output_file_format
        # defaultRenderGlobals
        dRG = pm.PyNode("defaultRenderGlobals")
        dRG.imageFilePrefix.set(render_file_rel_path)
        dRG.renderVersion.set("v%03d" % version.version_number)
        dRG.animation.set(1)
        dRG.outFormatControl.set(0)
        dRG.extensionPadding.set(4)
        dRG.imageFormat.set(7)  # force the format to iff
        dRG.pff.set(1)

        self.set_output_file_format()

    @classmethod
    def set_output_file_format(cls):
        """sets the output file format"""
        dRG = pm.PyNode("defaultRenderGlobals")

        # check the current renderer
        current_renderer = dRG.currentRenderer.get()
        if current_renderer == "mentalRay":
            # set the render output to OpenEXR with zip compression
            dRG.imageFormat.set(51)
            dRG.imfkey.set("exr")
            # check the maya version and set it if maya version is equal or
            # greater than 2012
            try:
                if pm.versions.current() >= pm.versions.v2012:
                    try:
                        mrG = pm.PyNode("mentalrayGlobals")
                    except pm.general.MayaNodeError:
                        #  the renderer is set to mentalray but it is not loaded
                        #  so there is no mentalrayGlobals
                        #  create them

                        # dirty little maya tricks
                        pm.mel.miCreateDefaultNodes()

                        #  get it again
                        mrG = pm.PyNode("mentalrayGlobals")

                    mrG.imageCompression.set(4)
            except (AttributeError, pm.general.MayaNodeError) as e:
                pass

            # if the renderer is not registered this causes a _objectError
            # and the frame buffer to 16bit half
            try:
                miDF = pm.PyNode("miDefaultFramebuffer")
                miDF.datatype.set(16)
            except (TypeError, pm.general.MayaNodeError) as e:
                # just don't do anything
                pass
        elif current_renderer == "arnold":
            dRG.imageFormat.set(51)  # exr
            try:
                dAD = pm.PyNode("defaultArnoldDriver")
                dAD.exrCompression.set(2)  # zips
                dAD.halfPrecision.set(1)  # half
                dAD.tiled.set(0)  # not tiled
                dAD.autocrop.set(1)  # will enhance file load times in Nuke
            except pm.MayaNodeError:
                # arnold has not rendered any single frame yet
                pass
        elif current_renderer == "redshift":
            try:
                dRO = pm.PyNode("redshiftOptions")
                dRO.imageFormat.set(1)
                dRO.exrBits.set(16)
                dRO.exrCompression.set(0)
                dRO.exrIsTiled.set(0)
                dRO.autocrop.set(1)
                # dRO.exrForceMultilayer.set(0)
                dRO.exrMultipart.set(0)
                dRO.noSaveImage.set(0)
                dRO.skipExistingFrames.set(1)
                # dRO.unifiedRandomizePattern.set(1)  # do not change this
                # try:
                #     dRO.enableOptiXRTOnSupportedGPUs.set(1)
                # except AttributeError:
                #     # should be RS2.x
                #     pass
            except pm.MayaNodeError:
                pass

    @classmethod
    def set_playblast_file_name(cls, version):
        """sets the playblast file name"""
        start = time.time()
        playblast_path = os.path.join(
            version.absolute_path, "Outputs", "Playblast"
        ).replace("\\", "/")

        playblast_filename = cls.get_significant_name(
            version, include_project_code=False
        )

        playblast_full_path = os.path.join(playblast_path, playblast_filename).replace(
            "\\", "/"
        )

        # create the folder
        try:
            os.makedirs(playblast_path)
        except OSError:
            # already exists
            pass

        pm.optionVar["playblastFile"] = playblast_full_path
        end = time.time()
        logger.debug("set_playblast_file_name() took %f seconds" % (end - start))

    @classmethod
    def set_render_resolution(cls, width, height, pixel_aspect=1.0):
        """Sets the resolution of the current scene

        :param width: The width of the output image
        :param height: The height of the output image
        :param pixel_aspect: The pixel aspect ratio
        """
        dRes = pm.PyNode("defaultResolution")
        dRes.width.set(width)
        dRes.height.set(height)
        dRes.pixelAspect.set(pixel_aspect)
        # also set the device aspect
        dRes.deviceAspectRatio.set(float(width) / float(height))

    @classmethod
    def set_project(cls, version):
        """Sets the project to the given version.

        The Maya version uses :class:`~stalker.models.version.Version`
        instances to set the project. Because the Maya workspace is related to
        the the Asset or Shot which can be derived from the Version instance
        very easily.
        """
        pm.workspace.open(version.absolute_path)
        # set the current timeUnit to match with the environments

        # set scene fps only if this scene is published or it is the first
        # version
        if version.is_published or version.version_number == 1:
            cls.set_fps(version.task.project.fps)

    @classmethod
    def is_in_repo(cls, path):
        """checks if the given path is in repository
        :param path: the path which wanted to be checked
        :return: True or False
        """
        from anima import __string_types__

        assert isinstance(path, __string_types__)
        path = os.path.expandvars(path)
        repo = cls.find_repo(path)
        return repo is not None

    @classmethod
    def move_to_local(cls, version, file_path, type_name):
        """moves the files to the local "external" path"""
        local_path = version.absolute_path + "/external_files/" + type_name
        filename = os.path.basename(file_path)
        destination_full_path = os.path.join(local_path, filename)
        # create the dirs
        try:
            os.makedirs(local_path)
        except OSError:  # dir exists
            pass

        if not os.path.exists(destination_full_path):
            # move the file
            logger.debug("moving to: %s" % destination_full_path)
            try:
                shutil.copy(file_path, local_path)
            except IOError:  # no write permission
                return None
            return destination_full_path
        else:  # file already exists do not overwrite
            logger.debug("file already exists, not moving")
            return None

    def check_external_files(self, version):
        """checks for external files in the current scene and raises
        RuntimeError if there are local files in the current scene, used as:

            - File Textures
            - Mentalray Textures
            - ImagePlanes
            - IBL nodes
            - References
        """
        start = time.time()
        # TODO: make this one a publish script
        external_nodes = []

        # check for audio files
        for audio in pm.ls(type=pm.nt.Audio):
            path = audio.filename.get()
            path = path.replace("\\", "/")
            logger.debug("checking path: %s" % path)
            if path is not None and os.path.isabs(path) and not self.is_in_repo(path):
                logger.debug("is not in repo: %s" % path)
                new_path = self.move_to_local(version, path, "Sound")
                if not new_path:
                    # it was not copied
                    external_nodes.append(audio)
                else:
                    # successfully copied
                    # update the path
                    logger.debug("updating audio path to: %s" % new_path)
                    audio.filename.set(new_path)

        # check for file textures
        for file_texture in pm.ls(type=pm.nt.File):
            path = file_texture.attr("fileTextureName").get()
            path = path.replace("\\", "/")
            logger.debug("checking path: %s" % path)
            if path is not None and os.path.isabs(path) and not self.is_in_repo(path):
                logger.debug("is not in repo: %s" % path)
                new_path = self.move_to_local(version, path, "Textures")
                if not new_path:
                    # it was not copied
                    external_nodes.append(file_texture)
                else:
                    # successfully copied
                    # update the path
                    logger.debug("updating texture path to: %s" % new_path)
                    file_texture.attr("fileTextureName").set(new_path)

        # check for arnold textures
        for arnold_texture in pm.ls(type="aiImage"):
            path = arnold_texture.attr("filename").get()
            path = path.replace("\\", "/")
            logger.debug("checking path: %s" % path)
            if path is not None and os.path.isabs(path) and not self.is_in_repo(path):
                logger.debug("is not in repo: %s" % path)
                new_path = self.move_to_local(version, path, "Textures")
                if not new_path:
                    # it was not copied
                    external_nodes.append(arnold_texture)
                else:
                    # successfully copied
                    # update the path
                    logger.debug("updating texture path to: %s" % new_path)
                    arnold_texture.attr("filename").set(new_path)

        # check for mentalray textures
        try:
            for mr_texture in pm.ls(type=pm.nt.MentalrayTexture):
                path = mr_texture.attr("fileTextureName").get()
                path = path.replace("\\", "/")
                logger.debug("path of %s: %s" % (mr_texture, path))
                if (
                    path is not None
                    and os.path.isabs(path)
                    and not self.is_in_repo(path)
                ):
                    logger.debug("is not in repo: %s" % path)
                    new_path = self.move_to_local(version, path, "Textures")
                    if not new_path:
                        # it was not copied
                        external_nodes.append(mr_texture)
                    else:
                        # successfully copied
                        # update the path
                        logger.debug("updating texture path to: %s" % new_path)
                        mr_texture.attr("fileTextureName").set(new_path)
        except AttributeError:  # MentalRay not loaded
            pass

        # check for ImagePlanes
        for image_plane in pm.ls(type=pm.nt.ImagePlane):
            path = image_plane.attr("imageName").get()
            path = path.replace("\\", "/")
            if path is not None and os.path.isabs(path) and not self.is_in_repo(path):
                logger.debug("is not in repo: %s" % path)
                new_path = self.move_to_local(version, path, "ImagePlanes")
                if not new_path:
                    # it was not copied
                    external_nodes.append(image_plane)
                else:
                    # successfully copied
                    # update the path
                    logger.debug("updating image plane path to: %s" % new_path)
                    image_plane.attr("imageName").set(new_path)

        # check for IBL nodes
        try:
            for ibl in pm.ls(type=pm.nt.MentalrayIblShape):
                path = ibl.attr("texture").get()
                path = path.replace("\\", "/")
                if (
                    path is not None
                    and os.path.isabs(path)
                    and not self.is_in_repo(path)
                ):
                    logger.debug("is not in repo: %s" % path)
                    new_path = self.move_to_local(version, path, "IBL")
                    if not new_path:
                        # it was not copied
                        external_nodes.append(ibl)
                    else:
                        # successfully copied
                        # update the path
                        logger.debug("updating ibl path to: %s" % new_path)
                        ibl.attr("texture").set(new_path)
        except AttributeError:  # mentalray not loaded
            pass

        if external_nodes:
            pm.select(external_nodes)
            raise RuntimeError(
                "There are missing external references in your scene!!!\n\n"
                "The problematic nodes are:\n\n"
                + ", ".join(map(lambda x: x.name(), external_nodes))
                + "\n\nThese nodes are added in to your selection list,\n"
                "Please correct them!\n\n"
                "YOUR FILE IS NOT GOING TO BE SAVED!!!"
            )

        end = time.time()
        logger.debug("check_external_files took %f seconds" % (end - start))

    def get_referenced_versions(self, parent_ref=None):
        """Returns the versions those are referenced to the current scene.

        :param parent_ref: The parent ref to start from. So the final list will
          be gathered from the references that are sub references of this
          parent ref.

        :returns: A list of Version instances
        """
        # get all the references
        logger.debug("getting references")
        references = pm.listReferences(parent_ref)

        # sort them according to path
        # to make same paths together
        logger.debug("sorting references")
        refs = sorted(references, key=lambda x: x.path)
        ref_count = len(references)

        # lets use a progress window
        caller = None
        if len(references):
            logger.debug("register a new caller")
            pdm = ProgressManager()
            caller = pdm.register(
                ref_count,
                "Maya.get_referenced_versions(%s) %i "
                "in total" % (parent_ref, ref_count),
            )

        prev_path = ""
        versions = []
        logger.debug("loop through %i references" % ref_count)
        for ref in refs:
            logger.debug("checking ref: %s" % ref.path)
            path = ref.path
            if path != prev_path:
                # try to get a version with the given path
                version = self.get_version_from_full_path(path)
                if version:
                    # check if this is a representation
                    if Representation.repr_separator in version.take_name:
                        # use the parent version
                        version = version.parent
                    if version and version not in versions:
                        versions.append(version)
                    prev_path = path
            if caller is not None:
                caller.step(message="path: %s" % path)
            logger.debug("stepping to next ref")

        if caller is not None:
            caller.end_progress()

        logger.debug("result: %s" % versions)
        return versions

    def update_first_level_versions(self, reference_resolution):
        """Updates the versions to the latest version.

        :param reference_resolution: A dictionary with keys 'leave', 'update'
          and 'create' with a list of :class:`~stalker.models.version.Version`
          instances in each of them. Only 'update' key is used and if the
          Version instance is in the 'update' list the reference is updated to
          the latest version.
        """
        # list only first level references
        references = sorted(pm.listReferences(), key=lambda x: x.path)

        # optimize it:
        #   do only one search for each references to the same version
        previous_ref_path = None
        previous_full_path = None

        updated_references = False

        from stalker import Repository

        for reference in references:
            path = reference.path
            if path == previous_ref_path:
                full_path = previous_full_path
            else:
                version = self.get_version_from_full_path(path)
                if version in reference_resolution["update"]:
                    latest_published_version = version.latest_published_version
                    full_path = latest_published_version.absolute_full_path
                else:
                    full_path = None

            if full_path:
                reference.replaceWith(Repository.to_os_independent_path(full_path))
                updated_references = True

        return updated_references

    def get_frame_range(self):
        """returns the current playback frame range"""
        start_frame = int(pm.playbackOptions(q=True, ast=True))
        end_frame = int(pm.playbackOptions(q=True, aet=True))
        return start_frame, end_frame

    def set_frame_range(self, start_frame=1, end_frame=100, adjust_frame_range=False):
        """sets the start and end frame range"""
        # set it in the playback
        pm.playbackOptions(ast=start_frame, aet=end_frame)

        if adjust_frame_range:
            pm.playbackOptions(min=start_frame, max=end_frame)

        # set in the render range
        dRG = pm.PyNode("defaultRenderGlobals")
        dRG.setAttr("startFrame", start_frame)
        dRG.setAttr("endFrame", end_frame)

    def get_fps(self):
        """returns the fps of the DCC"""
        return pm.mel.currentTimeUnitToFPS()

    @classmethod
    def set_fps(cls, fps=25.0):
        """Sets the fps of the DCC

        :param float fps: The FPS of the current DCC. Defaults to 25.
        """
        start = time.time()
        # get the current time, current playback min and max (because maya
        # changes them, try to restore the limits)
        current_time = pm.currentTime(q=1)
        pMin = pm.playbackOptions(q=1, min=1)
        pMax = pm.playbackOptions(q=1, max=1)
        pAst = pm.playbackOptions(q=1, ast=1)
        pAet = pm.playbackOptions(q=1, aet=1)

        # set the time unit, do not change the keyframe times
        # use the timeUnit as it is
        time_unit = "pal"

        # try to find a timeUnit for the given fps
        # prepare the time_to_fps table
        time_to_fps = {}
        regex = re.compile("[0-9\.]+")
        time_units = pm.mel.globals["gCurrentTimeCmdValueTable"]
        for time_unit in time_units:
            fps_string = pm.mel.internalTimeUnitStringToDisplayFPSString(
                time_unit
            ).replace(" ", "")
            fps_value = float(regex.findall(fps_string)[0])
            time_to_fps[time_unit] = fps_value

        # TODO: set it to the closest one
        for key in cls.time_to_fps:
            if cls.time_to_fps[key] == fps:
                time_unit = key
                break

        pm.currentUnit(t=time_unit, ua=0)
        # to be sure
        pm.optionVar["workingUnitTime"] = time_unit

        # update the playback ranges
        pm.currentTime(current_time)
        pm.playbackOptions(ast=pAst, aet=pAet)
        pm.playbackOptions(min=pMin, max=pMax)

        end = time.time()
        logger.debug("set_fps() took %f seconds" % (end - start))

    @classmethod
    def load_referenced_versions(cls):
        """loads all the references"""
        # get all the references
        for reference in pm.listReferences():
            reference.load()

    @classmethod
    def get_full_namespace_from_node_name(cls, node):
        """dirty way of getting the namespace from node name"""
        return ":".join((node.name().split(":"))[:-1])

    @classmethod
    def has_stereo_camera(cls):
        """checks if the scene has a stereo camera setup
        returns True if any
        """
        # check if the stereoCameraRig plugin is loaded
        if pm.pluginInfo("stereoCamera", q=True, l=True):
            return len(pm.ls(type="stereoRigTransform")) > 0
        else:
            # return False because it is impossible without stereoCamera plugin
            # to have a stereoCamera rig
            return False

    def replace_external_paths(self, mode=0):
        """Replaces all the external paths.

        Because absolute mode is the default and only mode, the 'mode' parameter is not used.

        replaces:
          * references
          * texture files including arnold textures
          * arnold ass paths
          * arnold aiVolume node path
          * image planes
          * and a lot of other nodes, just read the code...

        Absolute mode works best for now.

        .. note::

          The system doesn't care about the mentalrayTexture nodes because the lack of a good environment variable
          support from that node. Use regular maya file nodes with mib_texture_filter_lookup nodes to have the same
          sharp results.
        """
        start = time.time()
        workspace_path = pm.workspace.path

        logger.debug("replace_external_paths is called!!!")

        # *********************************************************************
        # References
        # replace reference paths with os independent absolute path
        from stalker import Repository

        for ref in pm.listReferences():
            unresolved_path = os.path.normpath(ref.unresolvedPath()).replace("\\", "/")

            # check if it is already containing some environment variables
            if "$" in unresolved_path:  # just skip this one
                logger.debug(
                    "skipping current ref, it is already os "
                    "independent!: %s" % unresolved_path
                )
                continue

            new_ref_path = Repository.to_os_independent_path(unresolved_path)
            if new_ref_path != unresolved_path:
                logger.info("replacing reference: %s" % ref.path)
                logger.info("replacing with: %s" % new_ref_path)
                ref.replaceWith(new_ref_path)

        # *********************************************************************
        # Texture Files
        # replace with absolute path

        # store node types and the attribute that is holding the path
        types_and_attrs = {
            "file": "fileTextureName",
            "imagePlane": "imageName",
            "audio": "filename",
            "AlembicNode": "abc_File",
            "gpuCache": "cacheFileName",
            # Arnold Nodes
            "aiImage": "filename",
            "aiStandIn": "filename",
            "aiVolume": "filename",
            # Redshift Nodes
            "RedshiftNormalMap": "tex0",
            "RedshiftProxyMesh": "fileName",
            "RedshiftDomeLight": ["tex0", "tex1"],
            "RedshiftSprite": "tex0",
        }

        for node_type in types_and_attrs.keys():
            attr_names = types_and_attrs[node_type]
            if not isinstance(attr_names, list):
                attr_names = [attr_names]

            for attr_name in attr_names:
                for node in pm.ls(type=node_type):
                    # # do not update if the node is a referenced node
                    # if node.referenceFile():
                    #     continue

                    orig_path = node.getAttr(attr_name)
                    if orig_path is None or orig_path == "" or "$" in orig_path:
                        # do nothing it is already using an environment variable
                        continue

                    logger.info("replacing file texture: %s" % orig_path)

                    path = os.path.normpath(os.path.expandvars(orig_path)).replace(
                        "\\", "/"
                    )

                    # be sure that it is not a Windows path
                    if ":" not in path:
                        # convert to absolute
                        if not os.path.isabs(path):  # be sure it
                            path = os.path.join(workspace_path, path).replace("\\", "/")

                    # convert to os independent absolute
                    new_path = Repository.to_os_independent_path(path)

                    if new_path != orig_path:
                        logger.info("with: %s" % new_path)

                        # check if it has any incoming connections
                        try:
                            inputs = node.attr(attr_name).inputs(p=1)
                        except TypeError as e:
                            inputs = []
                            print("ignoring this error: %s" % e)
                            print("node     : %s" % node.name())
                            print("attr_name: %s" % attr_name)

                        if len(inputs):
                            # it has incoming connections
                            # so set the other side
                            try:
                                inputs[0].set(new_path)
                            except RuntimeError:
                                pass
                        else:
                            try:
                                # preserve colorSpace info
                                color_space = None
                                has_color_space = node.hasAttr("colorSpace")
                                if has_color_space:
                                    color_space = node.colorSpace.get()
                                node.setAttr(attr_name, new_path)
                                if has_color_space:
                                    node.colorSpace.set(color_space)
                            except RuntimeError:
                                # it is probably locked
                                # just skip it
                                pass
        end = time.time()
        logger.debug("replace_external_paths took %f seconds" % (end - start))

    def create_workspace_file(self, path):
        """creates the workspace.mel at the given path"""
        start = time.time()
        content = self.maya_workspace_file_content

        # check if there is a workspace.mel at the given path
        full_path = os.path.join(path, "workspace.mel").replace("\\", "/")

        if not os.path.exists(full_path):
            try:
                os.makedirs(os.path.dirname(full_path))
            except OSError:
                # dir exists
                pass

        with open(full_path, "w") as workspace_file:
            workspace_file.write(content)

        end = time.time()
        logger.debug("create_workspace_file() took " "%f seconds" % (end - start))

    @classmethod
    def create_workspace_folders(cls, path):
        """creates the workspace folders

        :param path: the root of the workspace
        """
        start = time.time()
        for key in pm.workspace.fileRules:
            try:
                rule_path = pm.workspace.fileRules[key]
            except KeyError:
                continue
            full_path = os.path.join(path, rule_path).replace("\\", "/")
            # logger.debug(full_path)
            try:
                os.makedirs(full_path)
            except OSError:
                # dir exists
                pass
        end = time.time()
        logger.debug("create_workspace_folders() took %f seconds" % (end - start))

    def deep_version_inputs_update(self):
        """updates the inputs of the references of the current scene"""
        # first update with data from first level references
        self.update_version_inputs()

        # then go to the references
        references_list = pm.listReferences()

        prev_ref_path = None
        while len(references_list):
            current_ref = references_list.pop(0)
            logger.debug("current_ref: %s" % current_ref.path)
            self.update_version_inputs(current_ref)
            # optimize it by only appending one instance of the same referenced
            # file
            # sort the references according to their paths so, all the
            # references of the same file will be got together
            logger.debug("sorting references")
            all_refs = sorted(pm.listReferences(current_ref), key=lambda x: x.path)
            logger.debug("filtering references")
            for ref in all_refs:
                if ref.path != prev_ref_path:
                    prev_ref_path = ref.path
                    references_list.append(ref)

            prev_ref_path = None
            logger.debug("advancing to next ref")

    def check_referenced_versions(self, pdm=None):
        """Deeply checks all the references in the scene and returns a
        dictionary which has three keys called 'leave', 'update' and 'create'.

        Each of these keys correspond to a value of a list of
        :class:`~stalker.model.version.Version`\ s. Where the list in 'leave'
        key shows the Versions referenced (or deeply referenced) to the
        current scene which doesn't need to be changed.

        The list in 'update' key holds Versions those need to be updated to a
        newer version which are already exist.

        The list in 'create' key holds Version instance which needs to have its
        references to be updated to the never versions thus need a new version
        for them self.

        All the Versions in the list are sorted from the deepest to shallowest
        reference, so processing the list from 0th element to nth will always
        guarantee up to date info for the currently processed Version instance.

        Uses the top level references to get a Stalker Version instance and
        then tracks all the changes from these Version instances.

        :return: dictionary
        """
        pdm = ProgressManager()
        return super(Maya, self).check_referenced_versions(pdm=pdm)

    def update_versions(self, reference_resolution):
        """Updates maya versions with the given reference_resolution.

        The reference_resolution should be a dictionary in the following
        format::

          reference_resolution = {
              'root": [versionLM, versionUM, versionCM, ..., VersionXM],
              'leave': [versionL1, versionL2, ..., versionLN],
              'update': [versionU1, versionU2, ..., versionUN],
              'create': [versionC1, versionC2, ..., versionCN],
          }

        Previously this method was opening all the maya files by itself and do
        all the reference updates. But then we had crappy Maya scene files
        where the reference edits where ruined somehow. We tried to fix it by
        switching to a new update scheme (Shallow Reference Updates) but then
        we found that it is not working as expected. Finally, we have decided
        to update only 1st level references and inform the user about the
        deeper level references that needs to be updated and created UIs to let
        the artist quickly open the maya scene which needs to be updated. This
        way we hope that we still are going to have updated references and will
        prevent any bad maya scene file.

        All the references in the 'create' key need to be opened and then the
        all references need to be updated to the latest version and then a new
        :class:`~stalker.models.version.Version` instance will be created for
        each of them, and the newly created versions will be returned.

        The Version instances in 'leave' list will not be touched.

        The Version instances in 'update' list are there because the Version
        instances in 'create' list needs them to be updated. So practically
        these are Versions with already new versions so they will also not be
        touched.

        :param reference_resolution: A dictionary with keys 'leave', 'update'
          or 'create' and values of list of
          :class:`~stalker.models.version.Version` instances.
        :return list: A list of :class:`~stalker.models.version.Version`
          instances if created any.
        """
        logger.debug("updating to new versions with: %s" % reference_resolution)

        from stalker import Repository

        # just create a list from  first level references
        # and only update those references
        references_list = pm.listReferences()

        # order to the path
        references_list = sorted(references_list, key=lambda x: x.path)

        prev_path = ""
        prev_vers = None

        # use a progress window for that
        pdm = ProgressManager()
        caller = pdm.register(len(references_list), "Maya.update_versions()")

        # while len(references_list):
        for ref in references_list:
            # current_ref = references_list.pop(0)
            current_ref = ref

            current_ref_path = current_ref.path

            if current_ref_path != prev_path:
                # get current version
                current_version = self.get_version_from_full_path(current_ref_path)
                prev_vers = current_version
            else:
                current_version = prev_vers

            # update to a new version if present
            if current_version in reference_resolution["update"]:
                if not current_version.is_latest_published_version():
                    latest_published_version = current_version.latest_published_version

                    # replace the current reference with this one
                    current_ref.replaceWith(
                        Repository.to_os_independent_path(
                            latest_published_version.absolute_full_path
                        )
                    )

            caller.step(message=ref.namespace)

        return []  # no new version will be created with the current version

    def update_reference_edits(self, version):
        """Updates the reference edits for the given file

        :param version: The stalker.models.version.Version instance.
        :return: True or False depending on if a new namespace is created.
        """
        # This will be used to determine if we need to create a new
        # version for this version
        updated_namespaces = False
        # referenceQuery = pm.referenceQuery
        # use maya.cmds it is safer to use when there are Unicode edits
        referenceQuery = mc.referenceQuery

        regex = r"(?P<nice_name>[\w_0-9]+)" r"(?P<version>_v[0-9]+_ma[0-9]*)"

        # re open original scene
        reference_resolution = self.open(version, force=True)

        # check reference namespaces
        for ref in pm.listReferences(recursive=True):
            namespace = ref.namespace
            match = re.match(regex, namespace)
            if match:
                updated_namespaces = True

        if not updated_namespaces:
            # do updates
            return self.update_first_level_versions(reference_resolution)

        # check references
        refs = pm.listReferences(recursive=True)

        edits_dictionary = {}
        for i, ref in enumerate(reversed(refs)):
            # re apply any live edits
            try:
                # all_edits = referenceQuery(ref, es=1)
                all_edits = referenceQuery(ref.refNode.name(), es=True)
                if all_edits is None:
                    all_edits = []
            except UnicodeError:
                logger.debug("edits has improper character, skipping!!!")
                all_edits = []

            logger.debug("all_edits: %s" % all_edits)

            edits_dictionary[i] = {"namespace": ref.fullNamespace, "edits": all_edits}
            if all_edits:
                ref.removeReferenceEdits(force=1)
                ref.load()

        # do updates
        if self.update_first_level_versions(reference_resolution):
            updated_namespaces = True

        # replace first level reference namespaces
        for ref in pm.listReferences():
            # replace any possible old namespace with current one
            ref_version = self.get_version_from_full_path(ref.path)
            old_namespace = ref.namespace
            try:
                new_namespace = ref_version.nice_name

                # changing to the same namespace will change the namespace
                # to "namespace" to "namespace1"
                # prevent this by checking if the desired namespace is really
                # not the old_namespace
                if old_namespace != new_namespace:
                    ref.namespace = ref_version.nice_name
                    updated_namespaces = True

            except RuntimeError:
                # Apparently There is no namespace, so do not change the
                # namespace
                pass

        refs = pm.listReferences(recursive=True)
        for i, ref in enumerate(reversed(refs)):
            try:
                all_edits = edits_dictionary[i]["edits"]
            except KeyError:
                # there is a problem with this file skip this edit
                continue
            logger.debug("re-all_edits: %s" % all_edits)

            old_namespace = edits_dictionary[i]["namespace"]
            new_namespace = ref.fullNamespace

            logger.debug("old_namespace : %s" % old_namespace)
            logger.debug("new_namespace : %s" % new_namespace)

            # external edits, edits that are done in another scene
            external_edits = referenceQuery(ref, es=1, scs=1)

            for edit in all_edits:
                updated_edit = edit.replace(old_namespace, new_namespace).replace(
                    "|:", "|"
                )  # the last one is a weird bug

                # do not apply edits if they are coming from other scenes
                if updated_edit in external_edits:
                    continue

                logger.debug("updated_edit: %s" % updated_edit)
                # so this is an edit done in current scene
                try:
                    pm.mel.eval(updated_edit)
                except RuntimeError:
                    logger.debug("There is a RuntimeError in : %s" % updated_edit)
                    pass

        return updated_namespaces

    def fix_reference_namespaces(self):
        """Fixes the reference namespaces in current scene.

        This is a utility method to help fix the reference namespaces without
        loosing reference edits.

        The previous reference namespace template was including the version
        number and the file extension, and in a later version the Maya
        DCC started to use the ``version.nice_name`` as the namespace
        to let maya not to lose edits when new versions introduced.

        So basically this method finds the references with old namespaces no
        matter how deeply they are referenced and then creates new versions for
        the referencing version that uses the correct namespaces and then
        reapplies all the edits with tne new namespace.

        The returned list of versions `created_by` and `updated_by` attributes
        nee to be updated.

        :return: A list of newly created Versions
        """
        regex = r"(?P<nice_name>[\w_0-9]+)" r"(?P<version>_v[0-9]+_ma[0-9]*)"

        started_from_version = self.get_current_version()
        created_versions = []

        # get inverted reference nodes
        refs = reversed(pm.listReferences(recursive=1))

        to_update_list = []

        for ref in refs:
            # list every child ref of this ref
            update_this = False
            for child_ref in pm.listReferences(ref):
                # check the namespace
                namespace = child_ref.namespace
                match = re.match(regex, namespace)
                if match:
                    update_this = True
            if update_this:
                to_update_list.append(ref)

        # sort to_update_list according to ref.path
        # to_update_list = sorted(to_update_list, key=lambda x: x.path)

        to_update_paths = []

        for ref in to_update_list:
            path = ref.path
            if path not in to_update_paths:
                to_update_paths.append(path)
                # also add parents
                parent_ref = ref.parent()
                while parent_ref:
                    current_ref = parent_ref
                    path = current_ref.path
                    if path not in to_update_paths:
                        to_update_paths.append(path)
                    parent_ref = current_ref.parent()

        if to_update_paths:
            # so, we need to update things

            # we need to :
            # 1- open up these versions,
            # 2- fix the namespace
            # 3- and create a new version
            # 4- open the original scene
            # 5- store all the edits
            # 6- change namespace
            # 7- fix edits with new namespace
            # 8- apply them

            pdm = ProgressManager()
            caller = pdm.register(
                len(to_update_paths), "Maya.fix_reference_namespaces()"
            )

            from stalker import Version

            for path in to_update_paths:
                vers = self.get_version_from_full_path(path)

                logger.debug("vers: %s" % vers)
                if not vers:
                    continue

                # use the latest published version instead of the referenced
                # one, so we also do updates on the other hand
                vers = vers.latest_published_version
                logger.debug("vers.latest_published_version: %s" % vers)

                updated_namespaces = self.update_reference_edits(vers)

                logger.debug("updated_namespaces : %s" % updated_namespaces)
                if updated_namespaces:
                    # if we have changed the namespace we should create a new
                    # version
                    new_version = Version(
                        task=vers.task,
                        take_name=vers.take_name,
                        parent=vers,
                        description="Automatically created with Fix Reference "
                        "Namespace",
                    )
                    new_version.is_published = True
                    created_versions.append(new_version)
                    logger.debug("new_version : %s" % new_version)
                    self.save_as(new_version)
                    # pm.saveFile()

                caller.step(message=path)

            self.update_reference_edits(started_from_version)

        return created_versions

    @classmethod
    def remove_rogue_model_panel_change_events(cls):
        EVIL_METHOD_NAMES = [
            "DCF_updateViewportList",
            "CgAbBlastPanelOptChangeCallback",
            "onModelChange3dc",
            "look",
        ]
        capitalEvilMethodNames = [name.upper() for name in EVIL_METHOD_NAMES]
        modelPanelLabel = pm.mel.eval('localizedPanelLabel("ModelPanel")')
        processedPanelNames = []
        panelName = mc.sceneUIReplacement(getNextPanel=("modelPanel", modelPanelLabel))
        while panelName and panelName not in processedPanelNames:
            editorChangedValue = mc.modelEditor(
                panelName, query=True, editorChanged=True
            )
            parts = editorChangedValue.split(";")
            newParts = []
            changed = False
            for part in parts:
                for evilMethodName in capitalEvilMethodNames:
                    if evilMethodName in part.upper():
                        changed = True
                        break
                else:
                    newParts.append(part)
            if changed:
                mc.modelEditor(panelName, edit=True, editorChanged=";".join(newParts))
                print("Model panel error fixed!")
            processedPanelNames.append(panelName)
            panelName = mc.sceneUIReplacement(
                getNextPanel=("modelPanel", modelPanelLabel)
            )

    @classmethod
    def clean_malware(cls):
        """cleans malware"""
        malicious_node_names = ["vaccine_gene", "breed_gene"]
        for node_name in malicious_node_names:
            malicious_nodes = pm.ls("*%s*" % node_name)
            for node in malicious_nodes:
                try:
                    print("Found malicious node: %s" % node_name)
                    node.unlock()
                    pm.delete(node)
                    print("Deleted malicious node!")
                except pm.MayaNodeError:
                    pass

        # delete vaccine.py, userSetup.py
        user_app_dir = "%s/scripts" % pm.internalVar(userAppDir=True)
        malicious_script_file_names = [
            "vaccine.py",
            "vaccine.pyc",
            "userSetup.py",
            "userSetup.pyc",
        ]
        for malicious_script_file_name in malicious_script_file_names:
            malicious_script_file_full_path = os.path.join(
                user_app_dir, malicious_script_file_name
            )
            try:
                os.remove(malicious_script_file_full_path)
                print("Removed: %s" % malicious_script_file_full_path)
            except OSError:
                pass
