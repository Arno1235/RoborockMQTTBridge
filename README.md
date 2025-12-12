# RoborockMQTTBridge

````
cd RoborockMQTTBridge
buildah bud -t roborock_mqtt_bridge:arm .

# buildah push roborock_mqtt_bridge:arm oci-archive:roborock_mqtt_bridge-arm.tar
# sudo k3s ctr images import roborock_mqtt_bridge-arm.tar


buildah push roborock_mqtt_bridge:arm docker-archive:roborock_mqtt_bridge-arm.tar
sudo k3s ctr images import roborock_mqtt_bridge-arm.tar

sudo k3s ctr images tag localhost/roborock_mqtt_bridge:arm localhost:32000/roborock_mqtt_bridge:arm
sudo k3s ctr images push localhost:32000/roborock_mqtt_bridge:arm

````
