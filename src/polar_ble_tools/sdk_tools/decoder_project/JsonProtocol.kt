import com.polar.androidcommunications.api.ble.model.gatt.client.pmd.PmdMeasurementType
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import java.util.Base64
import kotlin.reflect.full.memberProperties

internal data class DecodeOutput(
    val recordCount: Int,
    val warnings: List<String>,
)

internal fun writeJsonl(
    destination: Path,
    type: PmdMeasurementType,
    source: ByteArray,
    data: Any,
): DecodeOutput {
    val warnings = linkedSetOf<String>()
    val adapted = adaptPayload(type, data, warnings)
    return publishAtomically(destination) { temporary ->
        var count = 0
        Files.newBufferedWriter(temporary, StandardCharsets.UTF_8).use { writer ->
            writer.write(
                jsonObject(
                    mapOf(
                        "type" to "header",
                        "protocol_version" to BuildInfo.PROTOCOL_VERSION,
                        "sdk_commit" to BuildInfo.SDK_COMMIT,
                        "decoder_version" to BuildInfo.DECODER_VERSION,
                        "source_sha256" to sha256(source),
                    ),
                    warnings,
                ),
            )
            writer.newLine()
            for (record in adapted.records) {
                writer.write(
                    jsonObject(
                        mapOf(
                            "type" to "record",
                            "record_type" to record.recordType,
                            "timestamp_ns" to record.timestampNs,
                            "payload" to record.payload,
                        ),
                        warnings,
                    ),
                )
                writer.newLine()
                count += 1
            }
            writer.write(
                jsonObject(
                    mapOf(
                        "type" to "summary",
                        "record_count" to count,
                        "record_types" to mapOf(adapted.recordType to count),
                        "warnings" to warnings.toList(),
                    ),
                    warnings,
                ),
            )
            writer.newLine()
        }
        DecodeOutput(count, warnings.toList())
    }
}

private fun jsonObject(
    value: Map<String, Any?>,
    warnings: MutableSet<String>,
): String =
    value.entries.joinToString(prefix = "{", postfix = "}") { (key, item) ->
        "${jsonString(key)}:${jsonValue(item, warnings)}"
    }

private fun jsonValue(
    value: Any?,
    warnings: MutableSet<String>,
    depth: Int = 0,
): String = when (value) {
    null -> "null"
    is String, is Char -> jsonString(value.toString())
    is Boolean, is Byte, is Short, is Int, is Long, is UByte, is UShort, is UInt ->
        value.toString()
    is ULong ->
        if (value <= Long.MAX_VALUE.toULong()) value.toString() else jsonString(value.toString())
    is Float -> finiteNumber(value.toDouble(), warnings)
    is Double -> finiteNumber(value, warnings)
    is Enum<*> -> jsonString(value.name.lowercase())
    is ByteArray ->
        jsonObject(
            mapOf(
                "encoding" to "base64",
                "data" to Base64.getEncoder().encodeToString(value),
            ),
            warnings,
        )
    is Map<*, *> ->
        value.entries.joinToString(prefix = "{", postfix = "}") { (key, item) ->
            val stringKey =
                key as? String
                    ?: throw UnsupportedRecordingError("JSON object keys must be strings")
            "${jsonString(jsonKey(stringKey))}:${jsonValue(item, warnings, depth + 1)}"
        }
    is Iterable<*> ->
        value.joinToString(prefix = "[", postfix = "]") {
            jsonValue(it, warnings, depth + 1)
        }
    is Array<*> ->
        value.joinToString(prefix = "[", postfix = "]") {
            jsonValue(it, warnings, depth + 1)
        }
    else -> {
        if (depth >= 16) {
            throw UnsupportedRecordingError("SDK value nesting exceeds 16 levels")
        }
        jsonObject(
            value::class.memberProperties.sortedBy { it.name }.associate {
                jsonKey(it.name) to readProperty(it, value)
            },
            warnings,
        )
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
            else ->
                if (character.code < 0x20) {
                    append("\\u%04x".format(character.code))
                } else {
                    append(character)
                }
        }
    }
    append('"')
}

private fun sha256(value: ByteArray): String =
    MessageDigest.getInstance("SHA-256")
        .digest(value)
        .joinToString("") { "%02x".format(it) }

internal fun printStatus(status: String, values: Map<String, Any>) {
    println(jsonObject(mapOf("status" to status) + values, linkedSetOf()))
}

internal fun printError(errorCode: String) {
    printStatus(
        "error",
        mapOf(
            "error_code" to errorCode,
            "protocol_version" to BuildInfo.PROTOCOL_VERSION,
            "sdk_commit" to BuildInfo.SDK_COMMIT,
            "decoder_version" to BuildInfo.DECODER_VERSION,
        ),
    )
}
