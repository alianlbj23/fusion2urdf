#Author-syuntoku14
#Description-Generate URDF file from Fusion 360

import adsk, adsk.core, adsk.fusion, traceback
import os
import sys
import shutil
from .utils import utils
from .utils.xacro2unity import convert_xacro_to_urdf
from .core import Link, Joint, Write
from pathlib import Path

"""
# length unit is 'cm' and inertial unit is 'kg/cm^2'
# If there is no 'body' in the root component, maybe the corrdinates are wrong.
"""

# joint effort: 100
# joint velocity: 100
# supports "Revolute", "Rigid" and "Slider" joint types

# I'm not sure how prismatic joint acts if there is no limit in fusion model

def run(context):
    ui = None
    success_msg = 'Successfully create URDF file'
    msg = success_msg

    try:
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

        root = design.rootComponent  # root component
        components = design.allComponents

        # set the names
        robot_name = root.name.split()[0]
        package_name = robot_name + '_description'
        save_dir = utils.file_dialog(ui)
        if save_dir == False:
            ui.messageBox('Fusion2URDF was canceled', title)
            return 0

        # Ask user if they want to clean up copied components
        cleanup_result = ui.messageBox(
            'Do you want to automatically clean up copied components after URDF generation?\n\n'
            'YES: Clean up (recommended) - removes temporary components created during export\n'
            'NO: Keep components - temporary components will remain in your Fusion file',
            title,
            adsk.core.MessageBoxButtonTypes.YesNoButtonType,
            adsk.core.MessageBoxIconTypes.QuestionIconType
        )
        cleanup_components = (cleanup_result == adsk.core.DialogResults.DialogYes)

        # If user selected an existing package folder, do not append again
        if os.path.basename(save_dir) != package_name:
            save_dir = save_dir + '/' + package_name
        try:
            os.makedirs(save_dir, exist_ok=True)
        except:
            pass

        package_dir = os.path.abspath(os.path.dirname(__file__)) + '/package/'

        # --------------------
        # set dictionaries

        # Generate joints_dict. All joints are related to root.
        joints_dict, msg = Joint.make_joints_dict(root, msg)
        if msg != success_msg:
            ui.messageBox(msg, title)
            return 0

        # Generate inertial_dict
        inertial_dict, msg = Link.make_inertial_dict(root, msg)
        if msg != success_msg:
            ui.messageBox(msg, title)
            return 0
        elif not 'base_link' in inertial_dict:
            msg = 'There is no base_link. Please set base_link and run again.'
            ui.messageBox(msg, title)
            return 0

        links_xyz_dict = {}

        # --------------------
        # Generate URDF
        Write.write_urdf(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_materials_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_transmissions_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_gazebo_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_display_launch(package_name, robot_name, save_dir)
        Write.write_gazebo_launch(package_name, robot_name, save_dir)
        Write.write_control_launch(package_name, robot_name, save_dir, joints_dict)
        Write.write_yaml(package_name, robot_name, save_dir, joints_dict)

        # copy over package files
        utils.copy_package(save_dir, package_dir)
        utils.update_cmakelists(save_dir, package_name)
        utils.update_package_xml(save_dir, package_name)

        # Generate STl files
        utils.copy_occs(root)
        utils.export_stl(design, save_dir, components)

        unity_urdf_dir = robot_name + "_unity_urdf"
        # Create unity urdf file directory under export folder
        unity_dir = Path(save_dir) / unity_urdf_dir
        unity_dir.mkdir(parents=True, exist_ok=True)
        # # Get xacro file
        xacro_file = save_dir + '/urdf/' + robot_name + '.xacro'
        convert_xacro_to_urdf(xacro_file=xacro_file,
                              output_urdf_path=str(unity_dir / (robot_name + '.urdf')))

        # Create package folder under unity_urdf_dir and copy meshes
        unity_package_dir = unity_dir / package_name
        unity_package_dir.mkdir(parents=True, exist_ok=True)
        src_meshes_dir = Path(save_dir) / 'meshes'
        dst_meshes_dir = unity_package_dir / 'meshes'
        try:
            if src_meshes_dir.exists():
                shutil.copytree(src_meshes_dir, dst_meshes_dir, dirs_exist_ok=True)
        except Exception as copy_error:
            msg += f'\nWarning: Failed to copy meshes: {str(copy_error)}'

        # Clean up copied components if user requested it
        if cleanup_components:
            try:
                utils.cleanup_copied_components(root)
                msg += '\nCopied components cleaned up successfully.'
            except Exception as cleanup_error:
                msg += f'\nWarning: Failed to clean up copied components: {str(cleanup_error)}'
        else:
            msg += '\nNote: Copied components were not cleaned up as requested.'
        msg += '\nFiles saved to: ' + save_dir


        ui.messageBox(msg, title)

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
