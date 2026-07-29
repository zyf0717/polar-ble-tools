import com.polar.androidcommunications.api.ble.model.gatt.client.pmd.PmdMeasurementType
import kotlin.reflect.KProperty1
import kotlin.reflect.full.memberProperties

private const val POLAR_EPOCH_UNIX_NS = 946_684_800_000_000_000L

internal data class AdaptedRecord(
    val recordType: String,
    val timestampNs: Long?,
    val payload: Map<String, Any>,
)

internal data class AdaptedPayload(
    val recordType: String,
    val records: Sequence<AdaptedRecord>,
)

internal fun adaptPayload(
    type: PmdMeasurementType,
    data: Any,
    warnings: MutableSet<String>,
): AdaptedPayload {
    val recordType = recordType(type)
    return AdaptedPayload(
        recordType,
        samples(data).map { (stream, sample) ->
            AdaptedRecord(
                recordType,
                timestampNs(type, sample, warnings),
                mapOf("stream" to stream, "sample" to sample),
            )
        },
    )
}

private fun samples(data: Any): Sequence<Pair<String, Any>> = sequence {
    var found = false
    for (property in data::class.memberProperties.sortedBy { it.name }) {
        val value = readProperty(property, data)
        if (value is Iterable<*>) {
            for (sample in value) {
                if (sample != null) {
                    found = true
                    yield(jsonKey(property.name) to sample)
                }
            }
        }
    }
    if (!found) {
        throw UnsupportedRecordingError("SDK result has no supported sample stream")
    }
}

@Suppress("UNCHECKED_CAST")
internal fun readProperty(property: KProperty1<out Any, *>, target: Any): Any? =
    (property as KProperty1<Any, *>).get(target)

private fun recordType(type: PmdMeasurementType): String = when (type) {
    PmdMeasurementType.ACC -> "acc"
    PmdMeasurementType.GYRO -> "gyro"
    PmdMeasurementType.MAGNETOMETER -> "magnetometer"
    PmdMeasurementType.OFFLINE_HR -> "hr"
    PmdMeasurementType.PPG -> "ppg"
    PmdMeasurementType.PPI -> "ppi"
    PmdMeasurementType.SKIN_TEMP -> "skin_temp"
    else -> throw UnsupportedRecordingError("unsupported measurement type: $type")
}

private fun timestampNs(
    type: PmdMeasurementType,
    sample: Any,
    warnings: MutableSet<String>,
): Long? {
    if (type == PmdMeasurementType.PPI) {
        warnings += "PPI timestamps are intentionally omitted pending validated SDK semantics"
        return null
    }
    val property =
        sample::class.memberProperties.singleOrNull { it.name == "timeStamp" } ?: return null
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

internal fun jsonKey(value: String): String = buildString {
    value.forEachIndexed { index, character ->
        if (character.isUpperCase()) {
            val previous = value.getOrNull(index - 1)
            val next = value.getOrNull(index + 1)
            if (
                index > 0 &&
                    previous != '_' &&
                    (!previous!!.isUpperCase() || next?.isLowerCase() == true)
            ) {
                append('_')
            }
            append(character.lowercaseChar())
        } else {
            append(character)
        }
    }
}
