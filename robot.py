import numpy as np
import math
import uuid
 
def rotationMatrixToEulerAngles(R) :     
    sy = math.sqrt(R[0,0] * R[0,0] +  R[1,0] * R[1,0])
     
    singular = sy < 1e-6
 
    if  not singular :
        x = math.atan2(R[2,1] , R[2,2])
        y = math.atan2(-R[2,0], sy)
        z = math.atan2(R[1,0], R[0,0])
    else :
        x = math.atan2(-R[1,2], R[1,1])
        y = math.atan2(-R[2,0], sy)
        z = 0
 
    return np.array([x, y, z])

def origin(matrix):
    urdf = '<origin xyz="%g %g %g" rpy="%g %g %g" />'
    x = matrix[0, 3]
    y = matrix[1, 3]
    z = matrix[2, 3]
    rpy = rotationMatrixToEulerAngles(matrix)

    return urdf % (x, y, z, rpy[0], rpy[1], rpy[2])

def pose(matrix, frame = ''):
    sdf = '<pose>%g %g %g %g %g %g</pose>'
    x = matrix[0, 3]
    y = matrix[1, 3]
    z = matrix[2, 3]
    rpy = rotationMatrixToEulerAngles(matrix)

    if frame != '':
        sdf = '<frame name="'+frame+'_frame">'+sdf+'</frame>'

    return sdf % (x, y, z, rpy[0], rpy[1], rpy[2])

class Robot(object):
    def __init__(self):
        self.drawCollisions = False
        self.relative = True
        self.xml = ''
        self.jointMaxEffort = 1
        self.jointMaxVelocity = 10
        self.noDynamics = False
    
    def append(self, str):
        self.xml += str+"\n"

    def jointMaxEffortFor(self, jointName):
        if isinstance(self.jointMaxEffort, dict):
            if jointName in self.jointMaxEffort:
                return self.jointMaxEffort[jointName]
            else:
                return self.jointMaxEffort['default']
        else:
            return self.jointMaxEffort

    def jointMaxVelocityFor(self, jointName):
        if isinstance(self.jointMaxVelocity, dict):
            if jointName in self.jointMaxVelocity:
                return self.jointMaxVelocity[jointName]
            else:
                return self.jointMaxVelocity['default']
        else:
            return self.jointMaxVelocity

class RobotURDF(Robot):
    def __init__(self):
        super().__init__()
        self.ext = 'urdf'
        self.append('<robot name="onshape">')
        pass

    def addDummyLink(self, name):
        self.append('<link name="'+name+'">')
        self.append('<inertial>')
        self.append('<origin xyz="0 0 0" rpy="0 0 0" />')
        # XXX: We use a low mass because PyBullet consider mass 0 as world fixed
        if self.noDynamics:
            self.append('<mass value="0" />')
        else:
            self.append('<mass value="1e-9" />')
        self.append('<inertia ixx="0" ixy="0" ixz="0" iyy="0" iyz="0" izz="0" />')
        self.append('</inertial>')
        self.append('</link>')

    def addFixedJoint(self, parent, child, matrix, name=None):
        if name is None:
            name = parent+'_'+child+'_fixing'

        self.append('<joint name="'+name+'" type="fixed">')
        self.append(origin(matrix))
        self.append('<parent link="'+parent+'" />')
        self.append('<child link="'+child+'" />')
        self.append('<axis xyz="0 0 0"/>')
        self.append('</joint>')
        self.append('')

    def startLink(self, name, matrix):
        self._link_name = name
        self._link_childs = 0
        self.addDummyLink(name)

    def endLink(self):
        pass

    def addFrame(self, name, matrix):
        # Adding a dummy link
        self.addDummyLink(name)

        # Linking it with last link with a fixed link
        self.addFixedJoint(self._link_name, name, matrix, name+'_frame')

    def addPart(self, matrix, stl, mass, com, inertia, color, shapes=None, name='', linkName=None):
        name = self._link_name+'_'+str(self._link_childs)+'_'+name
        if linkName is not None:
            name = linkName
        self._link_childs += 1

        self.append('<link name="'+name+'">')

        if not self.drawCollisions:
            # Visual
            self.append('<visual>')
            self.append('<geometry>')
            self.append('<mesh filename="package://'+stl+'"/>')
            self.append('</geometry>')
            self.append('<material name="'+name+'_material">')
            self.append('<color rgba="%g %g %g 1.0"/>' % (color[0], color[1], color[2]))
            self.append('</material>')
            self.append('</visual>')

        entries = ['collision']
        if self.drawCollisions:
            entries.append('visual')
        for entry in entries:
            
            if shapes is None:
                # We don't have pure shape, we use the mesh
                self.append('<'+entry+'>')
                self.append('<geometry>')
                self.append('<mesh filename="package://'+stl+'"/>')
                self.append('</geometry>')
                self.append('<material name="'+name+'_material">')
                self.append('<color rgba="%g %g %g 1.0"/>' % (color[0], color[1], color[2]))
                self.append('</material>')
                self.append('</'+entry+'>')
            else:
                # Inserting pure shapes in the URDF model
                for shape in shapes:
                        self.append('<'+entry+'>')
                        self.append(origin(shape['transform']))
                        self.append('<geometry>')
                        if shape['type'] == 'cube':
                            self.append('<box size="%g %g %g" />' % tuple(shape['parameters']))
                        if shape['type'] == 'cylinder':
                            self.append('<cylinder length="%g" radius="%g" />' % tuple(shape['parameters']))
                        if shape['type'] == 'sphere':
                            self.append('<sphere radius="%g" />' % shape['parameters'])
                        self.append('</geometry>')

                        self.append('<material name="'+name+'_material">')
                        self.append('<color rgba="%g %g %g 1.0"/>' % (color[0], color[1], color[2]))
                        self.append('</material>')
                        self.append('</'+entry+'>')

        self.append('<inertial>')
        self.append('<origin xyz="%g %g %g" rpy="0 0 0"/>' % (com[0], com[1], com[2]))
        self.append('<mass value="%g"/>' % mass)
        self.append('<inertia ixx="%g" ixy="%g"  ixz="%g" iyy="%g" iyz="%g" izz="%g" />' %
            (inertia[0], inertia[1], inertia[2], inertia[4], inertia[5], inertia[8]))
        self.append('</inertial>')
        self.append('</link>')

        self.addFixedJoint(self._link_name, name, matrix)


    def addJoint(self, linkFrom, linkTo, transform, name, zAxis=[0,0,1]):
        jointType = "continuous" if name.find('wheel') > 0 else "revolute"
        self.append('<joint name="'+name+'" type="'+jointType+'">')
        self.append(origin(transform))
        self.append('<parent link="'+linkFrom+'" />')
        self.append('<child link="'+linkTo+'" />')
        self.append('<axis xyz="%g %g %g"/>' % tuple(zAxis))
        self.append('<limit effort="%g" velocity="%g" />' % (self.jointMaxEffortFor(name), self.jointMaxVelocityFor(name)))
        self.append('<joint_properties friction="0.0"/>')
        self.append('</joint>')
        self.append('')
    
    def finalize(self):
        self.append('</robot>')


class RobotSDF(Robot):
    def __init__(self):
        super().__init__()
        self.ext = 'sdf'
        self.relative = False
        self.append('<sdf version="1.6">')
        self.append('<model name="onshape">')
        pass

    def addDummyLink(self, name):
        self.append('<link name="'+name+'">')
        self.append('<pose>0 0 0 0 0 0</pose>')
        self.append('<inertial>')
        self.append('<pose>0 0 0 0 0 0</pose>')
        self.append('<mass>1e-9</mass>')
        self.append('<inertia>')
        self.append('<ixx>0</ixx><ixy>0</ixy><ixz>0</ixz><iyy>0</iyy><iyz>0</iyz><izz>0</izz>')
        self.append('</inertia>')
        self.append('</inertial>')
        self.append('</link>')

    def addFixedJoint(self, parent, child, matrix, name=None):
        if name is None:
            name = parent+'_'+child+'_fixing'

        self.append('<joint name="'+name+'" type="fixed">')
        self.append(pose(matrix))
        self.append('<parent>'+parent+'</parent>')
        self.append('<child>'+child+'</child>')
        self.append('</joint>')
        self.append('')

    def startLink(self, name, matrix):
        self._link_name = name
        self._link_childs = 0
        self._dynamics = []
        # self.addDummyLink(name)
        self.append('<link name="'+name+'">')
        self.append(pose(matrix, name))

    def endLink(self):
        mass = 0
        com = np.array([0.0]*3)        
        inertia = np.matrix(np.zeros((3,3)))
        identity = np.matrix(np.eye(3))

        for dynamic in self._dynamics:
            mass += dynamic['mass']
            com += dynamic['com']*dynamic['mass']
        com /= mass

        # https://pybullet.org/Bullet/phpBB3/viewtopic.php?t=246
        for dynamic in self._dynamics:
            r = dynamic['com'] - com
            p = np.matrix(r)
            inertia += dynamic['inertia'] + (np.dot(r, r)*identity - p.T*p)*dynamic['mass']

        self.append('<inertial>')
        self.append('<pose frame="'+self._link_name+'_frame">%g %g %g 0 0 0</pose>' % (com[0], com[1], com[2]))
        self.append('<mass>%g</mass>' % mass)
        self.append('<inertia><ixx>%g</ixx><ixy>%g</ixy><ixz>%g</ixz><iyy>%g</iyy><iyz>%g</iyz><izz>%g</izz></inertia>' % (inertia[0, 0], inertia[0, 1], inertia[0, 2], inertia[1, 1], inertia[1, 2], inertia[2, 2]))
        self.append('</inertial>')

        self.append('</link>')
        self.append('')

    def addFrame(self, name, matrix):
        # Adding a dummy link
        self.addDummyLink(name)

        # Linking it with last link with a fixed link
        self.addFixedJoint(self._link_name, name, matrix, name+'_frame')

    def material(self, color):
        m = '<material>'
        m += '<ambient>%g %g %g 1</ambient>' % (color[0], color[1], color[2])
        m += '<diffuse>%g %g %g 1</diffuse>' % (color[0], color[1], color[2])
        m += '<specular>0.1 0.1 0.1 1</specular>'
        m += '<emissive>0 0 0 0</emissive>'
        m += '</material>'

        return m

    def addPart(self, matrix, stl, mass, com, inertia, color, shapes=None, name='', linkName=None):
        name = self._link_name+'_'+str(self._link_childs)+'_'+name
        if linkName is not None:
            name = linkName
        self._link_childs += 1

        # self.append('<link name="'+name+'">')
        # self.append(pose(matrix))

        if not self.drawCollisions:
            # Visual
            self.append('<visual name="'+name+'_visual">')
            self.append(pose(matrix))
            self.append('<geometry>')
            self.append('<mesh><uri>file://'+stl+'</uri></mesh>')
            self.append('</geometry>')
            self.append(self.material(color))
            self.append('</visual>')

        entries = ['collision']
        if self.drawCollisions:
            entries.append('visual')
        for entry in entries:
            
            if shapes is None:
                # We don't have pure shape, we use the mesh
                self.append('<'+entry+' name="'+name+'_'+entry+'">')
                self.append(pose(matrix))
                self.append('<geometry>')
                self.append('<mesh><uri>file://'+stl+'</uri></mesh>')
                self.append('</geometry>')
                if entry == 'visual': 
                    self.append(self.material(color))
                self.append('</'+entry+'>')
            else:
                # Inserting pure shapes in the URDF model
                k = 0
                for shape in shapes:
                    k += 1
                    self.append('<'+entry+' name="'+name+'_'+entry+'_'+str(k)+'">')
                    self.append(pose(shape['transform']))
                    self.append('<geometry>')
                    if shape['type'] == 'cube':
                        self.append('<box><size>%g %g %g</size></box>' % tuple(shape['parameters']))
                    if shape['type'] == 'cylinder':
                        self.append('<cylinder><length>%g</length><radius>%g</radius></cylinder>' % tuple(shape['parameters']))
                    if shape['type'] == 'sphere':
                        self.append('<sphere><radius>%g</radius></sphere>' % shape['parameters'])
                    self.append('</geometry>')

                    if entry == 'visual': 
                        self.append(self.material(color))
                    self.append('</'+entry+'>')

        # Inertia
        I = np.matrix(np.reshape(inertia[:9], (3, 3)))
        R = matrix[:3, :3]
        # Expressing COM in the link frame
        com = np.array((matrix*np.matrix([com[0], com[1], com[2], 1]).T).T)[0][:3]
        # Expressing inertia in the link frame
        inertia = R.T*I*R

        self._dynamics.append({
            'mass': mass,
            'com': com,
            'inertia': inertia
        })
        # self.append('</link>')

        # self.addFixedJoint(self._link_name, name, matrix)


    def addJoint(self, linkFrom, linkTo, transform, name, zAxis=[0,0,1]):
        self.append('<joint name="'+name+'" type="revolute">')
        self.append(pose(transform))
        self.append('<parent>'+linkFrom+'</parent>')
        self.append('<child>'+linkTo+'</child>')
        self.append('<axis>')
        self.append('<xyz>%g %g %g</xyz>' % tuple(zAxis))
        self.append('<limit><effort>%g</effort><velocity>%g</velocity></limit>' % (self.jointMaxEffortFor(name), self.jointMaxVelocityFor(name)))
        self.append('</axis>')
        self.append('</joint>')
        self.append('')
        # print('Joint from: '+linkFrom+' to: '+linkTo+', transform: '+str(transform))
    
    def finalize(self):
        self.append('</model>')
        self.append('</sdf>')
