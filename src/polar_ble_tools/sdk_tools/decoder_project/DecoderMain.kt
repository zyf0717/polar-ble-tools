import java.nio.file.Path

internal class UsageError(message: String) : RuntimeException(message)
internal class ProtocolCompatibilityError(message: String) : RuntimeException(message)
internal class UnsupportedRecordingError(message: String) : RuntimeException(message)
internal data class DecodeArguments(val input: Path, val output: Path, val protocol: Int)

fun main(arguments: Array<String>) {
    val exitCode = try {
        when (arguments.firstOrNull()) {
            "version" -> {
                requireArguments(arguments, 1)
                printStatus(
                    "ok",
                    mapOf(
                        "decoder_version" to BuildInfo.DECODER_VERSION,
                        "protocol_version" to BuildInfo.PROTOCOL_VERSION,
                        "sdk_commit" to BuildInfo.SDK_COMMIT,
                    ),
                )
                0
            }
            "self-test" -> {
                requireArguments(arguments, 1)
                check(BuildInfo.PROTOCOL_VERSION == 1)
                printStatus(
                    "ok",
                    mapOf(
                        "decoder_version" to BuildInfo.DECODER_VERSION,
                        "protocol_version" to BuildInfo.PROTOCOL_VERSION,
                        "sdk_commit" to BuildInfo.SDK_COMMIT,
                    ),
                )
                0
            }
            "decode" -> {
                val output = decodeRecording(parseDecodeArguments(arguments.drop(1)))
                printStatus(
                    "ok",
                    mapOf(
                        "decoder_version" to BuildInfo.DECODER_VERSION,
                        "protocol_version" to BuildInfo.PROTOCOL_VERSION,
                        "sdk_commit" to BuildInfo.SDK_COMMIT,
                        "record_count" to output.recordCount,
                        "warnings" to output.warnings,
                    ),
                )
                0
            }
            else -> throw UsageError(
                "expected: version | self-test | decode --input PATH --output PATH --protocol 1",
            )
        }
    } catch (error: UsageError) {
        System.err.println(error.message)
        printError("usage")
        2
    } catch (error: ProtocolCompatibilityError) {
        System.err.println(error.message)
        printError("protocol_incompatible")
        5
    } catch (error: UnsupportedRecordingError) {
        System.err.println(error.message)
        printError("unsupported_recording")
        3
    } catch (error: Exception) {
        System.err.println("decode failed: ${error.message ?: error::class.simpleName}")
        printError("decode_failed")
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
        val value = arguments.getOrNull(index + 1)
            ?: throw UsageError("missing value for ${arguments[index]}")
        when (arguments[index]) {
            "--input" -> input = Path.of(value)
            "--output" -> output = Path.of(value)
            "--protocol" -> protocol =
                value.toIntOrNull() ?: throw UsageError("protocol must be an integer")
            else -> throw UsageError("unknown argument: ${arguments[index]}")
        }
        index += 2
    }
    if (input == null || output == null || protocol == null) {
        throw UsageError("decode requires --input, --output, and --protocol")
    }
    return DecodeArguments(input, output, protocol)
}
