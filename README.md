# RoborockMQTTBridge

````
cd RoborockMQTTBridge
buildah bud -t roborock_mqtt_bridge3:arm . &&

buildah push roborock_mqtt_bridge3:arm docker-archive:roborock_mqtt_bridge3-arm.tar &&
sudo k3s ctr images import roborock_mqtt_bridge3-arm.tar &&

sudo k3s ctr images tag localhost/roborock_mqtt_bridge3:arm localhost:32000/roborock_mqtt_bridge3:arm &&
sudo k3s ctr images push localhost:32000/roborock_mqtt_bridge3:arm

````
