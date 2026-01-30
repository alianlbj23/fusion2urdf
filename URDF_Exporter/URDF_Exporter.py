# Author-syuntoku14
# Description-Generate URDF file from Fusion 360

import adsk, adsk.core, adsk.fusion, traceback
import os
import shutil
from pathlib import Path

from .utils import utils
from .utils.xacro2unity import convert_xacro_to_urdf
from .core import Link, Joint, Write

# -----------------------------
# Undo custom event (GLOBAL)
# -----------------------------
_UNDO_EVENT_ID = 'fusion2urdf_do_undo'
_undo_event = None
_undo_handler = None


class UndoEventHandler(adsk.core.CustomEventHandler):
    def notify(self, args):
        app = adsk.core.Application.get()
        try:
            app.executeTextCommand('NuCommands.UndoCmd')
        except:
            try:
                app.executeTextCommand('Commands.Start UndoCommand')
            except:
                pass


def ensure_undo_event():
    global _undo_event, _undo_handler
    app = adsk.core.Application.get()

    if _undo_event is None:
        _undo_event = app.registerCustomEvent(_UNDO_EVENT_ID)
        _undo_handler = UndoEventHandler()
        _undo_event.add(_undo_handler)


# -----------------------------
# Main entry
# -----------------------------
def run(context):
    ui = None
    success_msg = 'Successfully create URDF file'
    msg = success_msg

    try:
        # Ensure undo event exists
        ensure_undo_event()

        # --------------------
        # initialize
        app = adsk.core.Application.get()
        ui = app.userInterface
        product = app.activeProduct
        design = adsk.fusion.Design.cast(product)

        title = 'Fusion2URDF'
        if not design:
            ui.messageBox('No active Fusion design', title)
            return

        root = design.rootComponent
        components = design.allComponents

        # --------------------
        # naming
        robot_name = root.name.split()[0]
        package_name = robot_name + '_description'

        save_dir = utils.file_dialog(ui)
        if not save_dir:
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
            ui.messageBox(msg, title)
            return

        inertial_dict, msg = Link.make_inertial_dict(root, msg)
        if msg != success_msg:
            ui.messageBox(msg, title)
            return

        if 'base_link' not in inertial_dict:
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
        # cleanup copied components
        if cleanup_components:
            utils.cleanup_copied_components(root)
            msg += '\nCopied components cleaned up.'

        msg += f'\nFiles saved to:\n{save_dir}'
        ui.messageBox(msg, title)

        # --------------------
        # FINAL STEP: restore Fusion state
        # IMPORTANT: fire undo AFTER run() finishes
        app.fireCustomEvent(_UNDO_EVENT_ID)

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
