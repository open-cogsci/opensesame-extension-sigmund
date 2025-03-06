import sys
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget
from sigmund_qtwidget.sigmund_widget import SigmundWidget
import logging
logging.basicConfig(level=logging.debug)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sigmund")
        layout = QVBoxLayout()        
        sigmund_widget = SigmundWidget(self)
        sigmund_widget.start_server()
        layout.addWidget(sigmund_widget)
        self.setLayout(layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()    
    win.resize(1200, 800)
    win.show()
    sys.exit(app.exec_())
