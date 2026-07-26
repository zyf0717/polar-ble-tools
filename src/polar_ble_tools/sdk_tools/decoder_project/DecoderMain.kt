import com.polar.androidcommunications.api.ble.model.gatt.client.pmd.PmdMeasurementType
import com.polar.androidcommunications.api.ble.model.offlinerecording.OfflineRecordingData
import com.polar.androidcommunications.api.ble.model.offlinerecording.OfflineRecordingUtility
import java.nio.charset.StandardCharsets
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption.ATOMIC_MOVE
import java.nio.file.StandardCopyOption.REPLACE_EXISTING
import java.security.MessageDigest
import java.util.Base64
import kotlin.reflect.KProperty1
import kotlin.reflect.full.memberProperties

private const val PROTOCOL_VERSION = 1
private const val DECODER_VERSION = "0.1.1"
private const val SDK_COMMIT = "ccff6812c40fff1753c72385387d1877ca9b27b4"
private const val POLAR_EPOCH_UNIX_NS = 946_684_800_000_000_000L

private class UsageError(message: String) : RuntimeException(message)
private class UnsupportedRecordingError(message: String) : RuntimeException(message)
private data class DecodeArguments(val input: Path, val output: Path, val protocol: Int)
private data class DecodeOutput(val recordCount: Int, val warnings: List<String>)

fun main(arguments: Array<String>) {
    val exitCode = try {
        when (arguments.firstOrNull()) {
            "version" -> {
                requireArguments(arguments, 1)
                printStatus("ok", mapOf("decoder_version" to DECODER_VERSION, "protocol_version" to PROTOCOL_VERSION))
                0
            }
            "self-test" -> {
                requireArguments(arguments, 1)
                check(PROTOCOL_VERSION == 1)
                printStatus("ok", mapOf("decoder_version" to DECODER_VERSION, "protocol_version" to PROTOCOL_VERSION))
                0
            }
            "decode" -> {
                val output = decode(parseDecodeArguments(arguments.drop(1)))
                printStatus("ok", mapOf(
                    "decoder_version" to DECODER_VERSION,
                    "protocol_version" to PROTOCOL_VERSION,
                    "record_count" to output.recordCount,
                    "warnings" to output.warnings,
                ))
                0
            }
            else -> throw UsageError("expected: version | self-test | decode --input PATH --output PATH --protocol 1")
        }
    } catch (error: UsageError) {
        System.err.println(error.message)
        2
    } catch (error: UnsupportedRecordingError) {
        System.err.println(error.message)
        3
    } catch (error: Exception) {
        System.err.println("decode failed: ${error.message ?: error::class.simpleName}")
        4
    }
    if (exitCode != 0) kotlin.system.exitProcess(exitCode)
}

private fun requireArguments(arguments: Array<String>, expected: Int) {
    if (arguments.size != expected) throw UsageError("unexpected arguments")
}

private fun parseDecodeArguments(arguments: List<String>): DecodeArguments {
    var input: Path? = null
    var output: Path? = null
    var protocol: Int? = null
    var index = 0
    while (index < arguments.size) {
        val value = arguments.getOrNull(index + 1) ?: throw UsageError("missing value for ${arguments[index]}")
        when (arguments[index]) {
            "--input" -> input = Path.of(value)
            "--output" -> output = Path.of(value)
            "--protocol" -> protocol = value.toIntOrNull() ?: throw UsageError("protocol must be an integer")
            else -> throw UsageError("unknown argument: ${arguments[index]}")
        }
        index += 2
    }
    if (input == null || output == null || protocol == null) throw UsageError("decode requires --input, --output, and --protocol")
    return DecodeArguments(input, output, protocol)
}

private fun decode(arguments: DecodeArguments): DecodeOutput {
    if (arguments.protocol != PROTOCOL_VERSION) throw UnsupportedRecordingError("unsupported protocol ${arguments.protocol}")
    if (!Files.isRegularFile(arguments.input) || !Files.isReadable(arguments.input)) throw UsageError("input must be a readable regular file")
    if (Files.exists(arguments.output)) throw UsageError("output already exists: ${arguments.output}")
    val measurementType = try {
        OfflineRecordingUtility.mapOfflineRecordingFileNameToMeasurementType(arguments.input.fileName.toString())
    } catch (error: IllegalArgumentException) {
        throw UnsupportedRecordingError(error.message ?: "unsupported recording filename")
    }
    val source = Files.readAllBytes(arguments.input)
    val decoded = try {
        OfflineRecordingData.parseDataFromOfflineFile(source, measurementType)
    } catch (error: Exception) {
        throw UnsupportedRecordingError(error.message ?: "official SDK parser rejected recording")
    }
    return writeJsonl(arguments.output, measurementType, source, decoded.data)
}

private fun writeJsonl(destination: Path, type: PmdMeasurementType, source: ByteArray, data: Any): DecodeOutput {
    val parent = destination.toAbsolutePath().parent ?: throw UsageError("output must have a parent directory")
    val temporary = Files.createTempFile(parent, ".polar-rec-decoder-", ".jsonl")
    val warnings = linkedSetOf<String>()
    var count = 0
    try {
        Files.newBufferedWriter(temporary, StandardCharsets.UTF_8).use { writer ->
            writer.write(jsonObject(mapOf(
                "type" to "header", "protocol_version" to PROTOCOL_VERSION, "sdk_commit" to SDK_COMMIT,
                "decoder_version" to DECODER_VERSION, "source_sha256" to sha256(source),
            ), warnings))
            writer.newLine()
            for ((stream, sample) in samples(data)) {
                writer.write(jsonObject(mapOf(
                    "type" to "record", "record_type" to recordType(type),
                    "timestamp_ns" to timestampNs(sample, warnings),
                    "payload" to mapOf("stream" to stream, "sample" to sample),
                ), warnings))
                writer.newLine()
                count += 1
            }
            writer.write(jsonObject(mapOf(
                "type" to "summary", "record_count" to count,
                "record_types" to mapOf(recordType(type) to count), "warnings" to warnings.toList(),
            ), warnings))
            writer.newLine()
        }
        try {
            Files.move(temporary, destination, ATOMIC_MOVE)
        } catch (_: AtomicMoveNotSupportedException) {
            Files.move(temporary, destination, REPLACE_EXISTING)
        }
        return DecodeOutput(count, warnings.toList())
    } catch (error: Exception) {
        Files.deleteIfExists(temporary)
        throw error
    }
}

private fun samples(data: Any): List<Pair<String, Any>> {
    val result = mutableListOf<Pair<String, Any>>()
    for (property in data::class.memberProperties.sortedBy { it.name }) {
        val value = readProperty(property, data)
        if (value is Iterable<*>) value.filterNotNull().forEach { result += jsonKey(property.name) to it }
    }
    if (result.isEmpty()) result += "data" to data
    return result
}

@Suppress("UNCHECKED_CAST")
private fun readProperty(property: KProperty1<out Any, *>, target: Any): Any? = (property as KProperty1<Any, *>).get(target)

private fun recordType(type: PmdMeasurementType): String = when (type) {
    PmdMeasurementType.ACC -> "acc"
    PmdMeasurementType.ECG -> "ecg"
    PmdMeasurementType.GYRO -> "gyro"
    PmdMeasurementType.MAGNETOMETER -> "mag"
    PmdMeasurementType.OFFLINE_HR -> "hr"
    PmdMeasurementType.PPG -> "ppg"
    PmdMeasurementType.PPI -> "ppi"
    PmdMeasurementType.SKIN_TEMP -> "skin_temperature"
    PmdMeasurementType.TEMPERATURE -> "temperature"
    else -> "unknown"
}

private fun timestampNs(sample: Any, warnings: MutableSet<String>): Long? {
    val property = sample::class.memberProperties.singleOrNull { it.name == "timeStamp" } ?: return null
    val polarEpochNs = when (val value = readProperty(property, sample)) {
        is ULong -> if (value <= Long.MAX_VALUE.toULong()) value.toLong() else null
        is UInt -> value.toLong()
        is Long -> value.takeIf { it >= 0 }
        is Int -> value.toLong().takeIf { it >= 0 }
        else -> null
    }
    if (polarEpochNs == null || polarEpochNs > Long.MAX_VALUE - POLAR_EPOCH_UNIX_NS) {
        warnings += "SDK timestamp could not be represented as Unix nanoseconds"
        return null
    }
    return polarEpochNs + POLAR_EPOCH_UNIX_NS
}

private fun jsonKey(value: String): String = buildString {
    value.forEachIndexed { index, character ->
        if (character.isUpperCase()) {
            val previous = value.getOrNull(index - 1)
            val next = value.getOrNull(index + 1)
            if (index > 0 && previous != '_' && (!previous!!.isUpperCase() || next?.isLowerCase() == true)) append('_')
            append(character.lowercaseChar())
        } else append(character)
    }
}

private fun jsonObject(value: Map<String, Any?>, warnings: MutableSet<String>): String =
    value.entries.joinToString(prefix = "{", postfix = "}") { (key, item) -> "${jsonString(key)}:${jsonValue(item, warnings)}" }

private fun jsonValue(value: Any?, warnings: MutableSet<String>, depth: Int = 0): String = when (value) {
    null -> "null"
    is String, is Char -> jsonString(value.toString())
    is Boolean, is Byte, is Short, is Int, is Long, is UByte, is UShort, is UInt -> value.toString()
    is ULong -> if (value <= Long.MAX_VALUE.toULong()) value.toString() else jsonString(value.toString())
    is Float -> finiteNumber(value.toDouble(), warnings)
    is Double -> finiteNumber(value, warnings)
    is Enum<*> -> jsonString(value.name.lowercase())
    is ByteArray -> jsonObject(mapOf("encoding" to "base64", "data" to Base64.getEncoder().encodeToString(value)), warnings)
    is Map<*, *> -> value.entries.joinToString(prefix = "{", postfix = "}") { (key, item) ->
        val stringKey = key as? String
            ?: throw UnsupportedRecordingError("JSON object keys must be strings")
        "${jsonString(jsonKey(stringKey))}:${jsonValue(item, warnings, depth + 1)}"
    }
    is Iterable<*> -> value.joinToString(prefix = "[", postfix = "]") { jsonValue(it, warnings, depth + 1) }
    is Array<*> -> value.joinToString(prefix = "[", postfix = "]") { jsonValue(it, warnings, depth + 1) }
    else -> {
        if (depth >= 16) throw UnsupportedRecordingError("SDK value nesting exceeds 16 levels")
        jsonObject(value::class.memberProperties.sortedBy { it.name }.associate { jsonKey(it.name) to readProperty(it, value) }, warnings)
    }
}

private fun finiteNumber(value: Double, warnings: MutableSet<String>): String {
    if (!value.isFinite()) {
        warnings += "non-finite SDK number encoded as null"
        return "null"
    }
    return value.toString()
}

private fun jsonString(value: String): String = buildString {
    append('"')
    value.forEach { character ->
        when (character) {
            '"' -> append("\\\"")
            '\\' -> append("\\\\")
            '\b' -> append("\\b")
            '\u000C' -> append("\\f")
            '\n' -> append("\\n")
            '\r' -> append("\\r")
            '\t' -> append("\\t")
            else -> if (character.code < 0x20) append("\\u%04x".format(character.code)) else append(character)
        }
    }
    append('"')
}

private fun sha256(value: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(value).joinToString("") { "%02x".format(it) }

private fun printStatus(status: String, values: Map<String, Any>) {
    println(jsonObject(mapOf("status" to status) + values, linkedSetOf()))
}
