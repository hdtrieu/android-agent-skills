package example.mvi

data class LoadUiState(
    val items: List<String> = emptyList(),
    val isLoading: Boolean = false,
    val error: LoadError? = null,
    val requestId: Long? = null,
)

enum class LoadError { Unavailable }

sealed interface LoadAction {
    data object Refresh : LoadAction
    data object Retry : LoadAction
}

sealed interface LoadResult {
    data class Started(val requestId: Long) : LoadResult
    data class Loaded(val requestId: Long, val items: List<String>) : LoadResult
    data class Failed(val requestId: Long, val error: LoadError) : LoadResult
    data class Cancelled(val requestId: Long) : LoadResult
}

object LoadReducer {
    fun reduce(state: LoadUiState, result: LoadResult): LoadUiState = when (result) {
        is LoadResult.Started -> state.copy(
            isLoading = true,
            error = null,
            requestId = result.requestId,
        )
        is LoadResult.Loaded -> if (state.requestId == result.requestId) {
            state.copy(items = result.items.toList(), isLoading = false, error = null, requestId = null)
        } else {
            state
        }
        is LoadResult.Failed -> if (state.requestId == result.requestId) {
            state.copy(isLoading = false, error = result.error, requestId = null)
        } else {
            state
        }
        is LoadResult.Cancelled -> if (state.requestId == result.requestId) {
            state.copy(isLoading = false, error = null, requestId = null)
        } else {
            state
        }
    }
}
