import os
from PyQt5.QtWidgets import QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QObject, pyqtSlot
from PyQt5.QtWebChannel import QWebChannel

class ModelController(QObject):
    def __init__(self):
        super().__init__()
    
    @pyqtSlot(str)
    def log(self, message):
        print("Model Viewer:", message)

class AvatarWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.web_view = QWebEngineView(self)
        
        self.channel = QWebChannel()
        self.model_controller = ModelController()
        self.channel.registerObject("controller", self.model_controller)
        self.web_view.page().setWebChannel(self.channel)
        
        self.layout.addWidget(self.web_view)
        self.setLayout(self.layout)
        
        self.initialize_viewer()

    def initialize_viewer(self):
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.web_view.setHtml(self.get_viewer_html(), QUrl.fromLocalFile(base_path))

    def set_avatar_model(self, model_path):
        if os.path.exists(model_path):
            model_url = QUrl.fromLocalFile(os.path.abspath(model_path)).toString()
            js_code = f"loadModel('{model_url}')"
            self.web_view.page().runJavaScript(js_code)
        else:
            print(f"Model file not found: {model_path}")

    def set_background_image(self, image_path):
        """Set the background image for the viewer"""
        if os.path.exists(image_path):
            image_url = QUrl.fromLocalFile(os.path.abspath(image_path)).toString()
            js_code = f"setBackgroundImage('{image_url}')"
            self.web_view.page().runJavaScript(js_code)
        else:
            print(f"Background image not found: {image_path}")

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
        let backgroundTexture = null;
        
        function init() {
            loadingDiv = document.getElementById('loading');
            
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x2a2a2a);
            
            camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
            camera.position.set(0, 1.5, 3);
            
            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(window.innerWidth, window.innerHeight);
            document.body.appendChild(renderer.domElement);
            
            controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.target.set(0, 1, 0);
            
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
            scene.add(ambientLight);
            
            const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
            directionalLight.position.set(1, 1, 1);
            scene.add(directionalLight);
            
            animate();
            initWebChannel();
        }

        function setBackgroundImage(url) {
            if (!url) return;
            
            const textureLoader = new THREE.TextureLoader();
            textureLoader.load(
                url,
                function(texture) {
                    scene.background = texture;
                    
                    // Adjust texture to cover the background properly
                    const aspectRatio = window.innerWidth / window.innerHeight;
                    const imageAspectRatio = texture.image.width / texture.image.height;
                    
                    if (aspectRatio > imageAspectRatio) {
                        texture.repeat.set(1, imageAspectRatio / aspectRatio);
                        texture.offset.set(0, (1 - texture.repeat.y) / 2);
                    } else {
                        texture.repeat.set(aspectRatio / imageAspectRatio, 1);
                        texture.offset.set((1 - texture.repeat.x) / 2, 0);
                    }
                    
                    backgroundTexture = texture;
                    if (window.controller) {
                        window.controller.log("Background image loaded successfully");
                    }
                },
                undefined,
                function(error) {
                    console.error('Error loading background:', error);
                    if (window.controller) {
                        window.controller.log("Error loading background: " + error.message);
                    }
                }
            );
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
                    
                    const distance = Math.max(size.y * scale * 1.5, 2);
                    camera.position.set(0, size.y * scale * 0.8, distance); // Adjusted height multiplier
                    controls.target.set(0, size.y * scale * 0.6, 0); // Adjusted target height
                    controls.update();
                    
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
        
        function handleResize() {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
            
            // Update background texture scaling if it exists
            if (backgroundTexture) {
                const aspectRatio = window.innerWidth / window.innerHeight;
                const imageAspectRatio = backgroundTexture.image.width / backgroundTexture.image.height;
                
                if (aspectRatio > imageAspectRatio) {
                    backgroundTexture.repeat.set(1, imageAspectRatio / aspectRatio);
                    backgroundTexture.offset.set(0, (1 - backgroundTexture.repeat.y) / 2);
                } else {
                    backgroundTexture.repeat.set(aspectRatio / imageAspectRatio, 1);
                    backgroundTexture.offset.set((1 - backgroundTexture.repeat.x) / 2, 0);
                }
            }
        }
        
        window.addEventListener('resize', handleResize);
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
    
    # Load background and model after a short delay (for testing)
    from PyQt5.QtCore import QTimer
    def load_test_content():
        widget.set_background_image("background.jpeg")  # Replace with your background image path
        widget.set_avatar_model("models/chloe.glb")  # Replace with your model path
    QTimer.singleShot(1000, load_test_content)
    
    sys.exit(app.exec_())
