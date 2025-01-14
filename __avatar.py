import os
from PyQt5.QtWidgets import QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QObject, pyqtSlot
from PyQt5.QtWebChannel import QWebChannel

# Model Controller for Avatar
class ModelController(QObject):
    def __init__(self):
        super().__init__()
    
    @pyqtSlot(str)
    def log(self, message):
        print("Model Viewer:", message)

# Avatar Widget Class
class AvatarWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Initialize web view
        self.web_view = QWebEngineView(self)
        
        # Set up WebChannel for communication
        self.channel = QWebChannel()
        self.model_controller = ModelController()
        self.channel.registerObject("controller", self.model_controller)
        self.web_view.page().setWebChannel(self.channel)
        
        self.layout.addWidget(self.web_view)
        self.setLayout(self.layout)
        
        # Initialize with empty viewer
        self.initialize_viewer()

    def initialize_viewer(self):
        """Initialize the 3D viewer without loading a model"""
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.web_view.setHtml(self.get_viewer_html(), QUrl.fromLocalFile(base_path))

    def set_avatar_model(self, model_path):
        """Load a model into the viewer"""
        if os.path.exists(model_path):
            model_url = QUrl.fromLocalFile(os.path.abspath(model_path)).toString()
            js_code = f"loadModel('{model_url}')"
            self.web_view.page().runJavaScript(js_code)
        else:
            print(f"Model file not found: {model_path}")

    def get_viewer_html(self):
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { margin: 0; overflow: hidden; }
        canvas { display: block; }
        #loading {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 20px;
            border-radius: 10px;
            display: none;
        }
    </style>
</head>
<body>
    <div id="loading">Loading model...</div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    
    <script>
        let scene, camera, renderer, controls, mixer, model;
        let loadingDiv;
        
        function init() {
            loadingDiv = document.getElementById('loading');
            
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x2a2a2a);
            
            camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.z = 5;
            
            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            document.body.appendChild(renderer.domElement);
            
            controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
            scene.add(ambientLight);
            
            const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
            directionalLight.position.set(1, 1, 1);
            scene.add(directionalLight);
            
            animate();
            initWebChannel();
        }
        
        function initWebChannel() {
            if (typeof qt !== 'undefined' && qt.webChannelTransport) {
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    window.controller = channel.objects.controller;
                    if (window.controller) {
                        window.controller.log("Viewer initialized");
                    }
                });
            } else {
                setTimeout(initWebChannel, 100);
            }
        }
        
        function loadModel(url) {
            if (!url) return;
            
            loadingDiv.style.display = 'block';
            
            if (model) {
                scene.remove(model);
                if (mixer) {
                    mixer.stopAllAction();
                    mixer.uncacheRoot(model);
                }
            }
            
            const loader = new THREE.GLTFLoader();
            loader.load(
                url,
                function(gltf) {
                    model = gltf.scene;
                    scene.add(model);
                    
                    if (gltf.animations && gltf.animations.length) {
                        mixer = new THREE.AnimationMixer(model);
                        const action = mixer.clipAction(gltf.animations[0]);
                        action.play();
                    }
                    
                    const box = new THREE.Box3().setFromObject(model);
                    const center = box.getCenter(new THREE.Vector3());
                    const size = box.getSize(new THREE.Vector3());
                    const maxDim = Math.max(size.x, size.y, size.z);
                    const scale = 2 / maxDim;
                    model.scale.multiplyScalar(scale);
                    model.position.sub(center.multiplyScalar(scale));
                    
                    loadingDiv.style.display = 'none';
                    if (window.controller) {
                        window.controller.log("Model loaded successfully");
                    }
                },
                function(xhr) {
                    const percent = (xhr.loaded / xhr.total * 100).toFixed(2);
                    loadingDiv.textContent = `Loading model... ${percent}%`;
                },
                function(error) {
                    loadingDiv.style.display = 'none';
                    console.error('Error loading model:', error);
                    if (window.controller) {
                        window.controller.log("Error loading model: " + error.message);
                    }
                }
            );
        }
        
        function animate() {
            requestAnimationFrame(animate);
            controls.update();
            if (mixer) {
                mixer.update(0.016);
            }
            renderer.render(scene, camera);
        }
        
        window.addEventListener('resize', function() {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
        
        document.addEventListener('DOMContentLoaded', init);
    </script>
</body>
</html>
"""


# Example usage:
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    widget = AvatarWidget()
    widget.resize(800, 600)
    widget.show()
    
    # Load a model after a short delay (for testing)
    from PyQt5.QtCore import QTimer
    def load_test_model():
        widget.set_avatar_model("models/avatar.glb")  # Replace with your model path
    QTimer.singleShot(1000, load_test_model)
    
    sys.exit(app.exec_())