import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption.ATOMIC_MOVE
import java.nio.file.StandardCopyOption.REPLACE_EXISTING

internal fun <T> publishAtomically(destination: Path, write: (Path) -> T): T {
    val parent =
        destination.toAbsolutePath().parent
            ?: throw UsageError("output must have a parent directory")
    val temporary = Files.createTempFile(parent, ".polar-rec-decoder-", ".jsonl")
    try {
        val result = write(temporary)
        try {
            Files.move(temporary, destination, ATOMIC_MOVE)
        } catch (_: AtomicMoveNotSupportedException) {
            Files.move(temporary, destination, REPLACE_EXISTING)
        }
        return result
    } catch (error: Exception) {
        Files.deleteIfExists(temporary)
        throw error
    }
}
