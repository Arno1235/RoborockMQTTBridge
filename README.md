# RoborockMQTTBridge

```
cd RoborockMQTTBridge
buildah bud -t roborock_mqtt_bridge:arm . &&

buildah push roborock_mqtt_bridge:arm docker-archive:roborock_mqtt_bridge-arm.tar &&
sudo k3s ctr images import roborock_mqtt_bridge-arm.tar &&

sudo k3s ctr images tag localhost/roborock_mqtt_bridge:arm localhost:32000/roborock_mqtt_bridge:arm &&
sudo k3s ctr images push localhost:32000/roborock_mqtt_bridge:arm
```

```
kubectl -n iot create secret generic roborock-login --from-file=login.json
```
