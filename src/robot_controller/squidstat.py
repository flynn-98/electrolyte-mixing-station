import sys

from PySide6.QtWidgets import QApplication

# Import EIS specific package
from SquidstatPyLibrary import AisDeviceTracker, AisEISPotentiostaticElement, AisExperiment

# To communicate with: https://www.admiralinstruments.com/product-page/squidstat-plus-with-eis

experiment = AisExperiment()
eisElement = AisEISPotentiostaticElement(
    10000, # startFrequency
    1, # endFrequency
    10, # stepsPerDecade
    0.15, # voltageBias
    0.1 # voltageAmplitude
    )

experiment.appendElement(eisElement,1)
app = QApplication()
tracker = AisDeviceTracker.Instance()
 
tracker.newDeviceConnected.connect(lambda deviceName: print("Device is Connected: %s" % deviceName))
tracker.connectToDeviceOnComPort("COM19")
 
handler = tracker.getInstrumentHandler("Ace1102")
 
handler.activeDCDataReady.connect(lambda channel, data: print("timestamp:", "{:.9f}".format(data.timestamp), "workingElectrodeVoltage: ", "{:.9f}".format(data.workingElectrodeVoltage)))
handler.activeACDataReady.connect(lambda channel, data: print("frequency:", "{:.9f}".format(data.frequency), "absoluteImpedance: ", "{:.9f}".format(data.absoluteImpedance), "phaseAngle: ", "{:.9f}".format(data.phaseAngle)))
handler.experimentNewElementStarting.connect(lambda channel, data: print("New Node beginning:", data.stepName, "step number: ", data.stepNumber, " step sub : ", data.substepNumber))
handler.experimentStopped.connect(lambda channel : print("Experiment Completed: %d" % channel))
 
handler.uploadExperimentToChannel(0,experiment)
handler.startUploadedExperiment(0)

sys.exit(app.exec_())