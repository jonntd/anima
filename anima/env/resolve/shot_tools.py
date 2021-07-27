# -*- coding: utf-8 -*-
"""Shot related tools


from anima.env import blackmagic
resolve = blackmagic.get_resolve()
project_manager = resolve.GetProjectManager()
resolve_project = project_manager.GetCurrentProject()
timeline = resolve_project.GetCurrentTimeline()
clip = timeline.GetCurrentVideoItem()

"""
from anima import logger
from anima.ui.base import AnimaDialogBase
from anima.ui.lib import QtCore, QtWidgets


class ShotManager(object):
    """Manager for plate injection process

    Contains the general logic
    """

    def __init__(self, project=None, sequence=None):
        self.stalker_project = project
        self.stalker_sequence = sequence

        from anima.env import blackmagic
        self.resolve = blackmagic.get_resolve()
        self.project_manager = self.resolve.GetProjectManager()
        self.resolve_project = self.project_manager.GetCurrentProject()

    def get_current_shot_code(self):
        """returns the current shot code
        """
        shot_clip = self.get_current_shot()
        return shot_clip.shot_code

    def get_current_shot(self):
        """returns the current shot clip node
        """
        timeline = self.get_current_timeline()
        clip = self.get_current_clip()
        shot_clip = ShotClip()
        shot_clip.project = self.stalker_project
        shot_clip.sequence = self.stalker_sequence
        shot_clip.timeline = timeline
        shot_clip.clip = clip
        return shot_clip

    @classmethod
    def set_current_shot_code(cls, shot_code):
        """sets the current shot code

        :param str shot_code: The desired shot code
        """
        timeline = cls.get_current_timeline()

        shot_clip = ShotClip()
        shot_clip.clip = timeline.GetCurrentVideoItem()
        shot_clip.set_shot_code(shot_code)

    def get_current_clip(self):
        timeline = self.get_current_timeline()
        clip = timeline.GetCurrentVideoItem()
        return clip

    def get_current_timeline(self):
        timeline = self.resolve_project.GetCurrentTimeline()
        return timeline

    def get_clips(self):
        """returns the clips
        """
        timeline = self.get_current_timeline()
        clips = timeline.GetItemListInTrack('video', 1)
        return clips

    def get_shots(self):
        """returns the shots in the current video track
        """
        shots = []
        clips = self.get_clips()
        for clip in clips:
            pi = ShotClip(project=self.stalker_project, sequence=self.stalker_sequence, clip=clip, timeline=self.timeline)
            if pi.is_shot():
                shots.append(pi)
        return shots

    def generate_review_csv(self, output_path="", vendor=""):
        """Generates review CSV from the current timeline

        It searches for Fusion Clips and gathers information from the AnimaSlate nodes.

        :param str output_path: The path to output the CSV to.
        :param str vendor: The name of the vendor
        """
        from anima.utils import report
        data = ["Version Name,Link,Scope Of Work,Vendor,Submitting For,Submission Note"]

        clips = self.get_clips()
        for clip in clips:
            clip_data = list()
            media_pool_item = clip.GetMediaPoolItem()
            clip_name = media_pool_item.GetClipProperty("Clip Name")

            logger.debug("-------------------------")
            logger.debug("Checking: %s" % clip_name)

            # check if the current clip has a Fusion comp
            fusion_comp_count = clip.GetFusionCompCount()
            fusion_comp_name_list = clip.GetFusionCompNameList()
            logger.debug("fusion_comp_name_list: %s" % fusion_comp_name_list)
            if fusion_comp_count == 0:
                logger.debug("Fusion comp count: %s" % fusion_comp_count)
                continue

            slate_node = None
            for fusion_comp_name in fusion_comp_name_list:
                logger.debug("fusion_comp_count: %s" % fusion_comp_count)
                fusion_comp = clip.GetFusionCompByName(fusion_comp_name)

                if not fusion_comp:
                    logger.debug("No fusion_comp!")
                    continue
                logger.debug("fusion_comp: %s" % fusion_comp)

                # switch to Fusion tab
                slate_node = fusion_comp.FindTool("MainSlate")
                if slate_node:
                    logger.debug("found slate on: %s" % fusion_comp_name)
                    logger.debug("slate_node: %s" % slate_node)
                    break
                else:
                    logger.debug("no slate_node: %s" % fusion_comp_name)

            if slate_node is None:
                logger.debug("Still no slate!: %s" % clip_name)
                continue
            logger.debug("slate_node: %s" % slate_node)

            # Version Name
            # Use the clip name
            clip_data.append("%s.mov" % clip_name)

            # Link
            # Find the shot name
            version = report.NetflixReview.get_version_from_output(clip_name)
            shot = version.task.parent
            clip_data.append(shot.name)

            # Scope Of Work
            clip_data.append('"%s"' % shot.description)

            # Vendor
            clip_data.append(vendor)

            # Submitting For
            clip_data.append(slate_node.Input6[0])

            # Submission Note
            clip_data.append(slate_node.Input11[0].replace('\n', ' '))

            logger.debug("clip_data: %s" % clip_data)
            data.append(",".join(clip_data))

        logger.debug(data)
        with open(output_path, "w+") as f:
            f.write("\n".join(data))

    def finalize_review_csv(self, review_path=None, csv_output_path=None, vendor=None):
        """Finalizes the CSVs in the given review path by merging all the CSV's in to one and also generating data for
        the missing movie files.

        :param str review_path: The path to finalize.
        :param str csv_output_path: The finalized CSV path.
        :param str vendor: The vendor name
        :return:
        """
        import os
        import glob
        from anima.utils import report

        logger.debug("review_path    : %s" % review_path)
        logger.debug("csv_output_path: %s" % csv_output_path)
        logger.debug("vendor         : %s" % vendor)

        # get all the MOV files
        mov_files_in_folder = glob.glob("%s/*.mov" % review_path)
        logger.debug("mov files in folder")
        logger.debug("\n".join(mov_files_in_folder))

        # get all the CSV files
        csv_files = glob.glob("%s/*.csv" % review_path)
        logger.debug("csv files: %s" % csv_files)

        mov_files_from_csvs = []
        for csv_file in csv_files:
            with open(csv_file, 'r') as f:
                csv_data = f.readlines()

            for line in csv_data[1:]:
                data = line.split(',')
                video_file_name = data[0]
                mov_files_from_csvs.append(video_file_name)

        logger.debug("mov_files_from_csvs")
        logger.debug('\n'.join(mov_files_from_csvs))

        # skip all the files that are already listed in the CSV files
        filtered_mov_files = []
        for mov_file in mov_files_in_folder:
            mov_file_name = os.path.basename(mov_file)
            if mov_file_name not in mov_files_from_csvs:
                filtered_mov_files.append(mov_file)

        logger.debug("filtered_mov_files")
        logger.debug("\n".join(filtered_mov_files))

        nr = report.NetflixReview()
        nr.outputs = filtered_mov_files
        nr.generate_csv(csv_output_path, vendor=vendor, submission_note="")

        # now combine all the CSVs in to one
        combined_csv_data = ["Version Name,Link,Scope Of Work,Vendor,Submitting For,Submission Note"]
        csv_files = glob.glob("%s/*.csv" % review_path)
        for csv_file in csv_files:
            with open(csv_file, 'r') as f:
                csv_data = f.readlines()

            if csv_data:
                for line in csv_data[1:]:
                    if line:
                        combined_csv_data.append(line.strip())

        with open(csv_output_path, "w") as f:
            f.write("\n".join(combined_csv_data))

    def check_duplicate_shots(self):
        """checks for duplicate shots
        """
        shot_list = self.get_shots()
        shot_codes = []
        for shot in shot_list:
            shot_codes.append(shot.shot_code)
        shot_codes = sorted(shot_codes)
        unique_shot_codes = sorted(list(set(shot_codes)))
        duplicate_shot_codes = []
        if len(unique_shot_codes) != len(shot_codes):
            # find duplicate shot names
            prev_shot_code = ''
            for shot_code in shot_codes:
                current_shot_code = shot_code
                if current_shot_code == prev_shot_code:
                    duplicate_shot_codes.append(current_shot_code)
                prev_shot_code = current_shot_code

        return duplicate_shot_codes

    def validate_shot_codes(self):
        """validate shot codes
        """
        shots = self.get_shots()
        invalid_shots = []
        for shot in shots:
            try:
                shot.validate_shot_code()
            except ValueError:
                invalid_shots.append(shot)

        return invalid_shots

    def get_thumbnail(self):
        """returns the current media thumbnail
        """
        timeline = self.get_current_timeline()

        shot_clip = ShotClip()
        shot_clip.timeline = timeline
        shot_clip.clip = timeline.GetCurrentVideoItem()
        thumbnail = shot_clip.get_clip_thumbnail()
        return thumbnail


class ShotClip(object):
    """Manages Stalker Shots along with Resolve Clips

    Some of the functionalities that this class supplies:

      * Creates Stalker Shot hierarchy by looking at the shot related markers.
      * Generates render jobs that renders the VFX related clips in the current timeline to their respective shot
        folder.
      * Creates shot thumbnails that are visible through the system.
    """

    def __init__(self, project=None, sequence=None, clip=None, timeline=None):
        self.stalker_project = project
        self.stalker_sequence = sequence
        self.timeline = timeline
        self.clip = clip
        self._shot_code = None

    def create_shot_hierarchy(self):
        """creates the related shot hierarchy
        """
        logged_in_user = self.get_logged_in_user()

        from stalker import Task
        from stalker.db.session import DBSession
        shot = self.get_shot()
        if not shot:
            shot = self.create_shot()

        # creat shot tasks
        # Anim
        with DBSession.no_autoflush:
            anim_task = Task.query.filter(Task.parent == shot).filter(Task.name == 'Anim').first()
        if not anim_task:
            anim_task = Task(
                name='Anim',
                parent=shot,
                type=self.get_type('Animation'),
                bid_timing=10,
                bid_unit='min',
                created_by=logged_in_user,
                updated_by=logged_in_user,
                description='Autocreated by Resolve',
            )
            DBSession.add(anim_task)
            DBSession.commit()

        # Camera
        with DBSession.no_autoflush:
            camera_task = Task.query.filter(Task.parent == shot).filter(Task.name == 'Camera').first()
        if not camera_task:
            camera_task = Task(
                name='Camera',
                parent=shot,
                type=self.get_type('Camera'),
                bid_timing=10,
                bid_unit='min',
                created_by=logged_in_user,
                updated_by=logged_in_user,
                description='Autocreated by Resolve',
            )
            DBSession.add(camera_task)
            DBSession.commit()

        # Cleanup
        with DBSession.no_autoflush:
            cleanup_task = Task.query.filter(Task.parent == shot).filter(Task.name == 'Cleanup').first()
        if not cleanup_task:
            cleanup_task = Task(
                name='Cleanup',
                parent=shot,
                type=self.get_type('Cleanup'),
                bid_timing=10,
                bid_unit='min',
                created_by=logged_in_user,
                updated_by=logged_in_user,
                description='Autocreated by Resolve',
            )
            DBSession.add(cleanup_task)
            DBSession.commit()

        # Comp
        with DBSession.no_autoflush:
            comp_task = Task.query.filter(Task.parent == shot).filter(Task.name == 'Comp').first()
        if not comp_task:
            comp_task = Task(
                name='Comp',
                parent=shot,
                type=self.get_type('Comp'),
                bid_timing=10,
                bid_unit='min',
                created_by=logged_in_user,
                updated_by=logged_in_user,
                description='Autocreated by Resolve',
            )
            DBSession.add(comp_task)
            DBSession.commit()

        # Lighting
        with DBSession.no_autoflush:
            lighting_task = Task.query.filter(Task.parent == shot).filter(Task.name == 'Lighting').first()
        if not lighting_task:
            lighting_task = Task(
                name='Lighting',
                parent=shot,
                type=self.get_type('Lighting'),
                bid_timing=10,
                bid_unit='min',
                created_by=logged_in_user,
                updated_by=logged_in_user,
                description='Autocreated by Resolve',
            )
            DBSession.add(lighting_task)
            DBSession.commit()

        # Plate
        with DBSession.no_autoflush:
            plate_task = Task.query.filter(Task.parent == shot).filter(Task.name == 'Plate').first()
        if not plate_task:
            import datetime
            import pytz
            from stalker import defaults
            utc_now = datetime.datetime.now(pytz.utc)
            plate_task = Task(
                name='Plate',
                parent=shot,
                type=self.get_type('Plate'),
                schedule_timing=10,
                schedule_unit='min',
                schedule_model='duration',
                created_by=logged_in_user,
                updated_by=logged_in_user,
                description='Autocreated by Resolve',
                start=utc_now,  # this will be rounded to the timing resolution
                duration=defaults.timing_resolution
            )
            DBSession.add(plate_task)
            DBSession.commit()

        # Create a dummy version if there is non
        from stalker import Version
        with DBSession.no_autoflush:
            all_versions = Version.query.filter(Version.task == plate_task).all()

        if not all_versions:
            v = Version(
                task=plate_task,
                take_name='Main',  # TODO: use the track name as take
                created_by=logged_in_user,
                updated_by=logged_in_user,
                description='Autocreated by Resolve',
            )
            from anima.env import blackmagic
            resolve = blackmagic.get_resolve()
            version_info = resolve.GetVersion()
            v.created_with = 'Resolve%s.%s' % (version_info[0], version_info[1])
            DBSession.add(v)
            DBSession.commit()

        # set the status the task
        with DBSession.no_autoflush:
            from stalker import Status
            cmpl = Status.query.filter(Status.code == 'CMPL').first()
            plate_task.status = cmpl

        # Flush the DB first to prevent some empty id errors on already existing shots
        DBSession.commit()

        # add dependency relation
        from stalker.exceptions import StatusError
        with DBSession.no_autoflush:
            try:
                camera_task.depends = [plate_task]
            except StatusError as e:
                print(e)
                DBSession.rollback()
                pass

            try:
                anim_task.depends = [camera_task]
            except StatusError as e:
                print(e)
                DBSession.rollback()
                pass

            try:
                lighting_task.depends = [anim_task, camera_task]
            except StatusError as e:
                print(e)
                DBSession.rollback()
                pass

            try:
                cleanup_task.depends = [plate_task]
            except StatusError as e:
                print(e)
                DBSession.rollback()
                pass

            try:
                comp_task.depends = [lighting_task, plate_task]
            except StatusError as e:
                print(e)
                DBSession.rollback()
                pass

        DBSession.commit()

        return shot

    def get_shot(self):
        """returns the related Stalker Shot instance.
        """
        from stalker import Shot
        shot = Shot.query.filter(Shot.project == self.stalker_project).filter(Shot.code == self.shot_code).first()
        return shot

    def create_shot(self):
        """creates the related Stalker Shot entity with the current clip
        """
        from stalker import Shot, Task
        from stalker.db.session import DBSession
        # create the shot
        logged_in_user = self.get_logged_in_user()
        # FP_001_001_0010
        scene_code = self.shot_code.split("_")[2]
        scene_task = Task.query.filter(Task.parent == self.stalker_sequence).filter(Task.name.endswith(scene_code)).first()
        if not scene_task:
            # create the scene task
            scene_task = Task(
                project=self.stalker_project,
                name='SCN%s' % scene_code,
                type=self.get_type("Scene"),
                parent=self.stalker_sequence,
                description='Autocreated by Resolve',
                created_by=logged_in_user,
                updated_by=logged_in_user,
            )
            DBSession.add(scene_task)
            DBSession.commit()

        shots_task = Task.query.filter(Task.parent == scene_task).filter(Task.name == 'Shots').first()
        if not shots_task:
            shots_task = Task(
                project=self.stalker_project,
                name='Shots',
                parent=scene_task,
                description='Autocreated by Resolve',
                created_by=logged_in_user,
                updated_by=logged_in_user,
            )
            DBSession.add(shots_task)
            DBSession.commit()

        shot = Shot(
            name=self.shot_code,
            code=self.shot_code,
            project=self.stalker_project,
            parent=shots_task,
            sequences=[self.stalker_sequence],
            cut_in=1001,
            cut_out=int(self.clip.GetEnd() - self.clip.GetStart() + 1000),
            description='Autocreated by Resolve',
            created_by=logged_in_user,
            updated_by=logged_in_user,
        )
        DBSession.add(shot)
        DBSession.commit()
        return shot

    def update_shot_thumbnail(self):
        """updates the related shot thumbnail
        """
        thumbnail_full_path = self.get_clip_thumbnail()
        shot = self.get_shot()
        if not shot:
            shot = self.create_shot_hierarchy()
        from anima import utils
        return utils.upload_thumbnail(shot, thumbnail_full_path)

    def get_clip_thumbnail(self):
        """saves the thumbnail from resolve to a temp path and returns the path of the JPG file
        """
        # go to the color page to retrieve the thumbnail
        from anima.env import blackmagic
        resolve = blackmagic.get_resolve()
        current_page = resolve.GetCurrentPage()
        resolve.OpenPage('color')

        # pm = resolve.GetProjectManager()
        # ms = resolve.GetMediaStorage()
        # proj = resolve.GetCurrentProject()
        # mp = proj.GetMediaPool()

        # mp_item = self.clip.GetMediaPoolItem()
        # ms.RevealInStorage(self.clip.GetName())

        current_media_thumbnail = self.timeline.GetCurrentClipThumbnailImage()
        resolve.OpenPage(current_page)

        from PIL import Image
        import base64
        image = Image.frombytes(
            mode='RGB',
            size=[int(current_media_thumbnail['width']), int(current_media_thumbnail['height'])],
            data=base64.b64decode(current_media_thumbnail['data'])
        )

        import tempfile
        thumbnail_path = tempfile.mktemp(suffix='.jpg')
        image.save(thumbnail_path, quality=85)

        return thumbnail_path

    @classmethod
    def get_logged_in_user(cls):
        """returns the logged in user
        """
        # get logged in user
        from stalker import LocalSession
        from stalker.db.session import DBSession

        local_session = LocalSession()
        with DBSession.no_autoflush:
            logged_in_user = local_session.logged_in_user

        if not logged_in_user:
            raise RuntimeError("Please login first!")

        return logged_in_user

    def get_type(self, type_name):
        """returns the Stalker Type instance with the given name, if the type doesn't exist it will create it

        :param str type_name: Type queried type name

        :return:
        """
        from stalker.db.session import DBSession
        from stalker import Type
        with DBSession.no_autoflush:
            type_instance = Type.query.filter(Type.name == type_name).first()
        if not type_instance:
            logged_in_user = self.get_logged_in_user()
            type_instance = Type(
                entity_type='Task',
                name=type_name,
                created_by=logged_in_user,
                updated_by=logged_in_user
            )
            DBSession.add(type_instance)
            DBSession.commit()
        return type_instance

    def create_render_job(self):
        """creates render job for the clip
        """
        # create a new render output for each clip
        from anima.env import blackmagic
        resolve = blackmagic.get_resolve()

        pm = resolve.GetProjectManager()
        proj = pm.GetCurrentProject()

        template_name = "PlateInjector"
        result = proj.LoadRenderPreset(template_name)
        if not result:
            print("No template named: %s" % template_name)
        else:
            print("Template loaded successfully: %s" % template_name)

        # get the shot
        from stalker import Task, Type
        # shot = Shot.query.filter(Shot.project==self.stalker_project).filter(Shot.code==self.shot_code).first()
        # if not shot:
        #     # raise RuntimeError("No shot with code: %s" % self.shot_code)
        shot = self.create_shot_hierarchy()

        # get plate task
        plate_type = Type.query.filter(Type.name == 'Plate').first()
        if not plate_type:
            raise RuntimeError("No plate type!!!")

        from stalker.db.session import DBSession
        with DBSession.no_autoflush:
            plate_task = Task.query.filter(Task.parent == shot).filter(Task.type == plate_type).first()
        if not plate_task:
            raise RuntimeError("No plate task in shot: %s" % self.shot_code)

        proj.SetCurrentRenderFormatAndCodec('exr', 'RGBHalfZIP')

        version = plate_task.versions[-1]
        from stalker import Version
        assert isinstance(version, Version)
        version = version.latest_version
        assert isinstance(version, Version)
        from anima.env.base import EnvironmentBase
        version_sig_name = EnvironmentBase.get_significant_name(version, include_project_code=False)

        extension = version.extension
        version.update_paths()
        version.extension = extension

        import os
        custom_name = '%s.' % version_sig_name
        target_dir = os.path.join(
            version.absolute_path,
            'Outputs',
            version.take_name,
            'v%03d' % version.version_number,
            'exr'
        )

        proj.SetRenderSettings({
            'MarkIn': self.clip.GetStart(),
            'MarkOut': self.clip.GetEnd() - 1,
            'CustomName': custom_name,
            'TargetDir': target_dir
        })
        # proj.SetCurrentRenderMode(1)
        proj.AddRenderJob()

    def get_shot_related_marker(self):
        """returns the shot related marker data
        """
        clip_start_frame = self.clip.GetStart()
        timeline_start_frame = self.timeline.GetStartFrame()
        markers = self.timeline.GetMarkers()
        if markers:
            keys = markers.keys()
            frame_id = clip_start_frame - timeline_start_frame
            try:
                marker = markers[frame_id]
            except KeyError:
                return None

            marker['frameId'] = frame_id
            return marker

    def is_shot(self):
        """returns True if this is a shot clip
        """
        if self.shot_code:
            return True
        else:
            return False

    @property
    def shot_code(self):
        """Returns the shot code of the given clip

        :return:
        """
        if not self._shot_code:
            marker = self.get_shot_related_marker()
            if marker:
                self._shot_code = marker['note'].strip()

        return self._shot_code

    @shot_code.setter
    def shot_code(self, shot_code):
        """Sets the shot code of the given clip

        :return:
        """
        self._shot_code = None
        marker = self.get_shot_related_marker()

        if marker:
            self.timeline.DeleteMarkerAtFrame(marker['frameId'])

        # create a new marker
        result = self.timeline.AddMarker(
            frameId=self.clip.GetStart() - self.timeline.GetStartFrame(),
            color='Blue',
            name='Marker 1',
            note=shot_code,
            duration=1,
        )

        print("result: %s" % result)

    def validate_shot_code(self):
        """validates the shot code
        """
        import re
        regex = re.compile(r"([\w]+)_(\d{3})_(\d{3}[A-Z]{0,1})_(\d{4})")

        shot_code = self.shot_code
        match = regex.match(shot_code)
        if not match:
            raise ValueError("Shot code format is not valid: %s" % shot_code)

    def create_slate(self):
        """creates slate for this shot
        """
        # shot = self.get_shot()
        # if not shot:
        #     print("No valid shot!")
        #     return

        # Try to get a version with this clip path
        version_output_name = self.clip.GetName()
        version_file_name = version_output_name.split('.')[0]
        from stalker import Version, Task
        version = Version.query.join(Task, Version.task)\
            .filter(Version.full_path.contains(version_file_name))\
            .first()
        # .filter(Task.project == self.stalker_project)\

        if not version:
            print("No version output: %s" % version_output_name)
            return
        print("Found version from version_output: %s" % version)

        # we should be in good shape
        # create a new Fusion comp and run the magic commands
        from anima.env import blackmagic
        resolve = blackmagic.get_resolve()
        current_page = resolve.GetCurrentPage()
        resolve.OpenPage('fusion')
        slate_item = self.clip

        # Create the fusion comp
        # Remove any previous fusion comps of that clip
        fusion_comp_count = slate_item.GetFusionCompCount()
        print("slate_item.GetFusionCompCount(): %s" % fusion_comp_count)
        if fusion_comp_count != 0:
            print("Deleting all fusion compositions!")
            for fusion_comp_name in slate_item.GetFusionCompNameList():
                print("Deleting: %s" % fusion_comp_name)
                slate_item.DeleteFusionCompByName(fusion_comp_name)
            print("After deletion!")
            fusion_comp_count = slate_item.GetFusionCompCount()
            print("slate_item.GetFusionCompCount(): %s" % fusion_comp_count)

        fusion_comp = slate_item.AddFusionComp()
        print("Created fusion comp: %s" % fusion_comp)

        from anima.env import fusion
        f = fusion.Fusion()
        f.comp = fusion_comp
        slate_node = f.create_slate_node(version)

        resolve.OpenPage(current_page)
        return slate_node


class ShotToolsLayout(QtWidgets.QVBoxLayout, AnimaDialogBase):
    """The UI for the ShotManager
    """

    def __init__(self, *args, **kwargs):
        super(ShotToolsLayout, self).__init__(*args, **kwargs)
        self.form_layout = None
        self.project_combo_box = None
        self.sequence_combo_box = None
        self.setup_ui()

    def setup_ui(self):
        """sets the ui up
        """
        from anima.utils import do_db_setup
        do_db_setup()

        # get logged in user
        self.get_logged_in_user()

        # self.setWindowTitle("Shot Manager")
        self.form_layout = QtWidgets.QFormLayout(self.parent())
        self.addLayout(self.form_layout)

        i = 0
        # Project
        label = QtWidgets.QLabel(self.parent())
        label.setText("Project")
        self.form_layout.setWidget(
            i,
            QtWidgets.QFormLayout.LabelRole,
            label
        )

        from anima.ui.widgets.project import ProjectComboBox
        self.project_combo_box = ProjectComboBox(self.parent())
        self.form_layout.setWidget(
            i,
            QtWidgets.QFormLayout.FieldRole,
            self.project_combo_box
        )

        # Sequence
        i += 1
        label = QtWidgets.QLabel(self.parent())
        label.setText("Sequence")
        self.form_layout.setWidget(
            i,
            QtWidgets.QFormLayout.LabelRole,
            label
        )

        from anima.ui.widgets.sequence import SequenceComboBox
        self.sequence_combo_box = SequenceComboBox(self.parent())
        self.form_layout.setWidget(
            i,
            QtWidgets.QFormLayout.FieldRole,
            self.sequence_combo_box
        )

        # Get Shot List button
        get_shot_list_push_button = QtWidgets.QPushButton(self.parent())
        get_shot_list_push_button.setText("Get Shot List")
        self.addWidget(get_shot_list_push_button)

        # Check Duplicate Shot Code
        validate_shots_push_button = QtWidgets.QPushButton(self.parent())
        validate_shots_push_button.setText("Validate Shots")
        self.addWidget(validate_shots_push_button)

        # Check Duplicate Shot Code
        check_duplicate_shot_code_push_button = QtWidgets.QPushButton(self.parent())
        check_duplicate_shot_code_push_button.setText("Check Duplicate Shot Code")
        self.addWidget(check_duplicate_shot_code_push_button)

        # Create Render Jobs button
        create_render_jobs_button = QtWidgets.QPushButton(self.parent())
        create_render_jobs_button.setText("Create Render Jobs")
        self.addWidget(create_render_jobs_button)

        # Update Shot Thumbnail button
        update_shot_thumbnail_button = QtWidgets.QPushButton(self.parent())
        update_shot_thumbnail_button.setText("Update Shot Thumbnail")
        self.addWidget(update_shot_thumbnail_button)

        # Create Slate button
        create_slate_button = QtWidgets.QPushButton(self.parent())
        create_slate_button.setText("Create Slate")
        self.addWidget(create_slate_button)

        # Fix Shot Clip Name
        fix_shot_clip_name = QtWidgets.QPushButton(self.parent())
        fix_shot_clip_name.setText("Fix Shot Clip Names")
        self.addWidget(fix_shot_clip_name)
        fix_shot_clip_name.clicked.connect(self.fix_shot_clip_name)

        generate_review_csv_push_button = QtWidgets.QPushButton(self.parent())
        generate_review_csv_push_button.setText("Generate Review CSV")
        self.addWidget(generate_review_csv_push_button)
        generate_review_csv_push_button.clicked.connect(self.generate_review_csv)

        finalize_review_csv_push_button = QtWidgets.QPushButton(self.parent())
        finalize_review_csv_push_button.setText("Finalize Review CSV")
        self.addWidget(finalize_review_csv_push_button)
        finalize_review_csv_push_button.clicked.connect(self.finalize_review_csv)

        # ---------------------------------------------------------
        # Signals
        self.project_changed(None)
        self.project_combo_box.currentIndexChanged.connect(self.project_changed)

        create_render_jobs_button.clicked.connect(self.create_render_jobs)
        get_shot_list_push_button.clicked.connect(self.get_shot_list)
        check_duplicate_shot_code_push_button.clicked.connect(self.check_duplicate_shots)
        validate_shots_push_button.clicked.connect(self.validate_shot_codes)
        update_shot_thumbnail_button.clicked.connect(self.update_shot_thumbnail)
        create_slate_button.clicked.connect(self.create_slate)

        self.addStretch()

    def project_changed(self, index):
        """runs when the current selected project has been changed
        """
        self.sequence_combo_box.project = self.project_combo_box.get_current_project()

    def get_shot_list(self):
        """just prints the shot names
        """
        project = self.project_combo_box.get_current_project()
        sequence = self.sequence_combo_box.get_current_sequence()
        im = ShotManager(project, sequence)
        for shot in im.get_shots():
            isinstance(shot, ShotClip)
            print(shot.shot_code)

    def create_render_jobs(self):
        """creates render jobs
        """
        # first check duplicate shots
        if not self.check_duplicate_shots():
            return

        if not self.validate_shot_codes():
            return

        project = self.project_combo_box.get_current_project()
        sequence = self.sequence_combo_box.get_current_sequence()
        im = ShotManager(project, sequence)

        message_box = QtWidgets.QMessageBox(self.parent())
        # message_box.setTitle("Which Shots?")
        message_box.setText("Which Shots?")

        current_shot = QtWidgets.QPushButton("Current")
        all_shots = QtWidgets.QPushButton("All")

        message_box.addButton(current_shot, QtWidgets.QMessageBox.YesRole)
        message_box.addButton(all_shots, QtWidgets.QMessageBox.NoRole)

        message_box.exec_()

        try:
            clicked_button = message_box.clickedButton()
            message_box.deleteLater()
            if clicked_button == all_shots:
                for shot in im.get_shots():
                    shot.create_render_job()
            else:
                im.get_current_shot().create_render_job()
        except BaseException as e:
            QtWidgets.QMessageBox.critical(
                self.parent(),
                "Error",
                str(e)
            )
            raise e
        finally:
            QtWidgets.QMessageBox.information(
                self.parent(),
                "Created Shots and Render Jobs 👍",
                "Created Shots and Render Jobs 👍"
            )

    def validate_shot_codes(self):
        """validates the shot codes
        """
        project = self.project_combo_box.get_current_project()
        sequence = self.sequence_combo_box.get_current_sequence()
        im = ShotManager(project, sequence)
        invalid_shots = im.validate_shot_codes()
        invalid_shot_codes = []
        for shot in invalid_shots:
            invalid_shot_codes.append(shot.shot_code)

        if invalid_shot_codes:
            QtWidgets.QMessageBox.critical(
                self.parent(),
                "Invalid shot names!!!",
                "There are invalid shot codes:<br>%s" % "<br>".join(invalid_shot_codes)
            )
            return False
        else:
            QtWidgets.QMessageBox.information(
                self.parent(),
                "All shots valid 👍",
                "All shots valid 👍"
            )
            return True

    def check_duplicate_shots(self):
        """checks for duplicate shot code
        """
        project = self.project_combo_box.get_current_project()
        sequence = self.sequence_combo_box.get_current_sequence()
        im = ShotManager(project, sequence)
        duplicate_shot_codes = im.check_duplicate_shots()
        if duplicate_shot_codes:
            QtWidgets.QMessageBox.critical(
                self.parent(),
                "Duplicate Shot Codes!!!",
                "There are duplicate shot codes:<br>%s" % "<br>".join(duplicate_shot_codes)
            )
            return False
        else:
            QtWidgets.QMessageBox.information(
                self.parent(),
                "No Duplicate Shots 👍",
                "No duplicate shots 👍"
            )
            return True

    def update_shot_thumbnail(self):
        """updates the current shot thumbnail with the clip thumbnail from resolve
        """
        project = self.project_combo_box.get_current_project()
        sequence = self.sequence_combo_box.get_current_sequence()
        im = ShotManager(project, sequence)
        shot = im.get_current_shot()

        try:
            shot.update_shot_thumbnail()
        except BaseException as e:
            QtWidgets.QMessageBox.critical(
                self.parent(),
                "Shot thumbnail could not be updated",
                str(e)
            )
        else:
            QtWidgets.QMessageBox.information(
                self.parent(),
                "Updated shot thumbnail 👍",
                "Updated shot thumbnail 👍"
            )

    def create_slate(self):
        """creates slate for the current shot
        """
        project = self.project_combo_box.get_current_project()
        sequence = self.sequence_combo_box.get_current_sequence()
        im = ShotManager(project, sequence)
        shot = im.get_current_shot()
        if shot:
            shot.create_slate()

    def fix_shot_clip_name(self):
        """Removes the frame range part from the image sequence clips.
        """
        project = self.project_combo_box.get_current_project()
        sequence = self.sequence_combo_box.get_current_sequence()
        im = ShotManager(project, sequence)
        for clip in im.get_clips():
            media_pool_item = clip.GetMediaPoolItem()
            clip_name = media_pool_item.GetClipProperty("Clip Name")
            print("clip_name: %s" % clip_name)
            new_clip_name = clip_name.split(".")[0]
            print("new_clip_name: %s" % new_clip_name)
            media_pool_item.SetClipProperty("Clip Name", new_clip_name)

    def generate_review_csv(self):
        """generates review CSVs from the slate clips in the current timeline
        """
        import os
        import tempfile
        default_path_storage = os.path.join(tempfile.gettempdir(), "last_csv_file_path")
        default_path = os.path.expanduser("~")
        try:
            with open(default_path_storage, "r") as f:
                default_path = f.read()
        except IOError:
            pass

        # show a file browser
        csv_file_path = QtWidgets.QFileDialog.getSaveFileName(self.parent(), "Choose CSV Path", default_path, "CSV (*.csv)")[0]
        print("csv_file_path: %s" % csv_file_path)

        if not csv_file_path:
            raise RuntimeError("no file path chosen!")

        # save the path
        with open(default_path_storage, "w") as f:
            f.write(csv_file_path)

        from anima.utils import do_db_setup
        do_db_setup()
        from stalker import Studio
        studio = Studio.query.first()
        studio_name = studio.name if studio else ""

        sm = ShotManager(None, None)
        sm.generate_review_csv(output_path=csv_file_path, vendor=studio_name)

    def finalize_review_csv(self):
        """finalizes the review CSVs in the given path
        """
        import os
        import tempfile
        default_path_storage = os.path.join(tempfile.gettempdir(), "last_csv_folder_path")
        default_path = os.path.expanduser("~")
        try:
            with open(default_path_storage, "r") as f:
                default_path = f.read()
        except IOError:
            pass

        # show a file browser
        csv_folder_path = QtWidgets.QFileDialog.getExistingDirectory(self.parent(), "Choose CSV Path", default_path)
        print("csv_folder_path: %s" % csv_folder_path)

        if not csv_folder_path:
            raise RuntimeError("no folder path chosen!")

        # save the path
        with open(default_path_storage, "w") as f:
            f.write(csv_folder_path)

        from anima.utils import do_db_setup
        do_db_setup()
        from stalker import Studio
        studio = Studio.query.first()
        studio_name = studio.name if studio else ""

        # output to the same folder with the folder name as csv
        dir_name = os.path.basename(csv_folder_path)
        csv_output_path = os.path.join(csv_folder_path, "%s.csv" % dir_name)

        sm = ShotManager(None, None)
        sm.finalize_review_csv(review_path=csv_folder_path, csv_output_path=csv_output_path, vendor=studio_name)
