# Author-syuntoku14
# Description-Generate URDF file from Fusion 360

import adsk
import adsk.core
import adsk.fusion
import traceback
import os
import shutil
from pathlib import Path

from .utils import utils
from .utils.xacro2unity import convert_xacro_to_urdf
from .core import Link, Joint, Write

# -----------------------------
# Undo / rollback (GLOBAL)
# -----------------------------
_UNDO_EVENT_ID = 'fusion2urdf_do_undo'
_undo_event = None
_undo_handler = None

# Used by fallback cleanup when undo/rollback fails
_undo_root = None

# Rollback control
_start_marker_index = None
_need_rollback = False


class UndoEventHandler(adsk.core.CustomEventHandler):
    def notify(self, args):
        """
        Fallback undo behavior:
        1) Try text-command undo (works in most builds)
        2) If that fails, attempt legacy undo command
        3) If undo fails, cleanup copied components (best effort)
        """
        app = adsk.core.Application.get()
        try:
            app.executeTextCommand('NuCommands.UndoCmd')
            return
        except:
            try:
                app.executeTextCommand('Commands.Start UndoCommand')
                return
            except:
                pass

        # Final fallback: cleanup copied components if undo fails
        try:
            global _undo_root
            if _undo_root is not None:
                utils.cleanup_copied_components(_undo_root)
        except:
            pass


def ensure_undo_event():
    """
    Register a custom event to execute undo at the very end of the script if needed.
    """
    global _undo_event, _undo_handler
    app = adsk.core.Application.get()

    if _undo_event is None:
        _undo_event = app.registerCustomEvent(_UNDO_EVENT_ID)
        _undo_handler = UndoEventHandler()
        _undo_event.add(_undo_handler)


def _get_timeline_marker_index(design: adsk.fusion.Design) -> int:
    """
    Record the current timeline marker position index.
    Different Fusion builds expose markerPosition differently, so we try several options.
    """
    try:
        tl = design.timeline
    except:
        return None

    # Preferred: markerPosition has an index
    try:
        marker = tl.markerPosition
        if hasattr(marker, 'index'):
            return int(marker.index)
    except:
        pass

    # Fallback: use the current timeline end as an approximate anchor
    try:
        return int(tl.count)
    except:
        return None


def _try_set_timeline_marker(design: adsk.fusion.Design, marker_index: int) -> bool:
    """
    Try to move timeline marker back to a given index.
    Returns True if success, False otherwise.
    """
    if marker_index is None:
        return False

    try:
        tl = design.timeline
    except:
        return False

    # Bound marker_index to valid range
    try:
        count = int(tl.count)
        if marker_index < 0:
            marker_index = 0
        if marker_index > count:
            marker_index = count
    except:
        pass

    # Some builds accept setting markerPosition to a timeline object
    try:
        tl.markerPosition = tl.item(marker_index)
        return True
    except:
        pass

    # Some builds accept setting markerPosition to an integer
    try:
        tl.markerPosition = marker_index
        return True
    except:
        pass

    return False


def _rollback_to_start(app: adsk.core.Application, design: adsk.fusion.Design, marker_index: int) -> bool:
    """
    Best-effort rollback to the state at the start of run():
    1) Try timeline marker rollback (cleanest)
    2) If not available, try repeated Undo (less deterministic)
    Returns True if we believe rollback succeeded.
    """
    # 1) Timeline rollback
    if _try_set_timeline_marker(design, marker_index):
        return True

    # 2) Undo fallback (bounded)
    # NOTE: This may undo beyond script changes depending on the user's prior state.
    # We cap the loop to avoid infinite undo.
    for _ in range(200):
        try:
            app.executeTextCommand('NuCommands.UndoCmd')
            return True
        except:
            try:
                app.executeTextCommand('Commands.Start UndoCommand')
                return True
            except:
                pass

    return False


# -----------------------------
# Main entry
# -----------------------------
def run(context):
    ui = None
    app = None
    product = None
    design = None
    root = None
    components = None

    success_msg = 'Successfully create URDF file'
    msg = success_msg

    # Ensure undo event exists (used only as fallback)
    ensure_undo_event()

    # Default behavior: rollback unless we explicitly mark success
    global _need_rollback, _start_marker_index
    _need_rollback = True
    _start_marker_index = None

    try:
        # --------------------
        # initialize
        app = adsk.core.Application.get()
        ui = app.userInterface
        product = app.activeProduct
        design = adsk.fusion.Design.cast(product)

        title = 'Fusion2URDF'
        if not design:
            if ui:
                ui.messageBox('No active Fusion design', title)
            return

        root = design.rootComponent
        components = design.allComponents

        # Share root for fallback cleanup
        global _undo_root
        _undo_root = root

        # Record the "start state" marker before doing anything that may modify the design
        _start_marker_index = _get_timeline_marker_index(design)

        # --------------------
        # naming
        robot_name = root.name.split()[0]
        package_name = robot_name + '_description'

        save_dir = utils.file_dialog(ui)
        if not save_dir:
            if ui:
                ui.messageBox('Fusion2URDF was canceled', title)
            return

        # Ask cleanup
        cleanup_result = ui.messageBox(
            'Do you want to automatically clean up copied components after URDF generation?\n\n'
            'YES: Clean up (recommended)\n'
            'NO: Keep components',
            title,
            adsk.core.MessageBoxButtonTypes.YesNoButtonType,
            adsk.core.MessageBoxIconTypes.QuestionIconType
        )
        cleanup_components = (cleanup_result == adsk.core.DialogResults.DialogYes)

        if os.path.basename(save_dir) != package_name:
            save_dir = os.path.join(save_dir, package_name)

        os.makedirs(save_dir, exist_ok=True)
        package_dir = os.path.join(os.path.dirname(__file__), 'package')

        # --------------------
        # generate dictionaries
        joints_dict, msg = Joint.make_joints_dict(root, msg)
        if msg != success_msg:
            if ui:
                ui.messageBox(msg, title)
            return

        inertial_dict, msg = Link.make_inertial_dict(root, msg)
        if msg != success_msg:
            if ui:
                ui.messageBox(msg, title)
            return

        if 'base_link' not in inertial_dict:
            if ui:
                ui.messageBox('There is no base_link. Please set base_link and run again.', title)
            return

        links_xyz_dict = {}

        # --------------------
        # write URDF / xacro / launch
        Write.write_urdf(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_materials_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_transmissions_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_gazebo_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_display_launch(package_name, robot_name, save_dir)
        Write.write_gazebo_launch(package_name, robot_name, save_dir)
        Write.write_control_launch(package_name, robot_name, save_dir, joints_dict)
        Write.write_yaml(package_name, robot_name, save_dir, joints_dict)

        utils.copy_package(save_dir, package_dir)
        utils.update_cmakelists(save_dir, package_name)
        utils.update_package_xml(save_dir, package_name)

        # --------------------
        # STL export (THIS MODIFIES DESIGN)
        utils.copy_occs(root)
        utils.export_stl(design, save_dir, components)

        # --------------------
        # Unity URDF
        unity_dir = Path(save_dir) / f'{robot_name}_unity_urdf'
        unity_dir.mkdir(parents=True, exist_ok=True)

        xacro_file = os.path.join(save_dir, 'urdf', f'{robot_name}.xacro')
        convert_xacro_to_urdf(
            xacro_file=xacro_file,
            output_urdf_path=str(unity_dir / f'{robot_name}.urdf')
        )

        unity_package_dir = unity_dir / package_name
        unity_package_dir.mkdir(parents=True, exist_ok=True)

        src_meshes = Path(save_dir) / 'meshes'
        dst_meshes = unity_package_dir / 'meshes'
        if src_meshes.exists():
            shutil.copytree(src_meshes, dst_meshes, dirs_exist_ok=True)

        # --------------------
        # cleanup copied components (design may still be rolled back later if failure occurs after this point)
        if cleanup_components:
            utils.cleanup_copied_components(root)
            msg += '\nCopied components cleaned up.'

        msg += f'\nFiles saved to:\n{save_dir}'
        if ui:
            ui.messageBox(msg, title)

        # If we reached here, we consider the run successful, so do not rollback
        _need_rollback = False

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
        # Keep _need_rollback = True so we rollback in finally
    finally:
        # --------------------
        # FINAL STEP: restore Fusion state on any error or early-return (unless marked success)
        try:
            if app is None:
                app = adsk.core.Application.get()

            # Only rollback if this run did not complete successfully
            if _need_rollback and design is not None and _start_marker_index is not None:
                rolled_back = _rollback_to_start(app, design, _start_marker_index)

                # If rollback fails, fallback to custom undo event (best effort)
                if not rolled_back:
                    app.fireCustomEvent(_UNDO_EVENT_ID)

            # If marker is unavailable, still try the fallback undo event on failure
            elif _need_rollback:
                app.fireCustomEvent(_UNDO_EVENT_ID)

            try:
                adsk.doEvents()
            except:
                pass

        except:
            # Never throw from finally
            pass
