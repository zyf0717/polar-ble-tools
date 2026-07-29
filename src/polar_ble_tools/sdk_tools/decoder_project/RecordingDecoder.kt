import com.polar.androidcommunications.api.ble.model.offlinerecording.OfflineRecordingData
import com.polar.androidcommunications.api.ble.model.offlinerecording.OfflineRecordingUtility
import java.nio.file.Files

internal fun decodeRecording(arguments: DecodeArguments): DecodeOutput {
    if (arguments.protocol != BuildInfo.PROTOCOL_VERSION) {
        throw ProtocolCompatibilityError("unsupported protocol ${arguments.protocol}")
    }
    if (!Files.isRegularFile(arguments.input) || !Files.isReadable(arguments.input)) {
        throw UsageError("input must be a readable regular file")
    }
    if (Files.exists(arguments.output)) {
        throw UsageError("output already exists: ${arguments.output}")
    }
    val measurementType = try {
        OfflineRecordingUtility.mapOfflineRecordingFileNameToMeasurementType(
            arguments.input.fileName.toString(),
        )
    } catch (error: IllegalArgumentException) {
        throw UnsupportedRecordingError(
            error.message ?: "unsupported recording filename",
        )
    }
    val source = Files.readAllBytes(arguments.input)
    val decoded = try {
        OfflineRecordingData.parseDataFromOfflineFile(source, measurementType)
    } catch (error: Exception) {
        throw UnsupportedRecordingError(
            error.message ?: "official SDK parser rejected recording",
        )
    }
    return writeJsonl(arguments.output, measurementType, source, decoded.data)
}
