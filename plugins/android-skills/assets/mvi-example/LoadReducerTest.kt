package example.mvi

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class LoadReducerTest {
    @Test
    fun refreshRetainsContentAndClearsPreviousError() {
        val state = LoadUiState(items = listOf("old"), error = LoadError.Unavailable)
        val actual = LoadReducer.reduce(state, LoadResult.Started(1))
        assertThat(actual).isEqualTo(
            LoadUiState(items = listOf("old"), isLoading = true, requestId = 1),
        )
    }

    @Test
    fun successReplacesContentAndFinishesRequest() {
        val state = LoadUiState(isLoading = true, requestId = 1)
        assertThat(LoadReducer.reduce(state, LoadResult.Loaded(1, listOf("new"))))
            .isEqualTo(LoadUiState(items = listOf("new")))
    }

    @Test
    fun failurePreservesContentForRetry() {
        val state = LoadUiState(items = listOf("old"), isLoading = true, requestId = 1)
        val actual = LoadReducer.reduce(state, LoadResult.Failed(1, LoadError.Unavailable))
        assertThat(actual).isEqualTo(
            LoadUiState(items = listOf("old"), error = LoadError.Unavailable),
        )
    }

    @Test
    fun oldResponseCannotOverwriteNewRequest() {
        val state = LoadUiState(items = listOf("old"), isLoading = true, requestId = 2)
        assertThat(LoadReducer.reduce(state, LoadResult.Loaded(1, listOf("stale"))))
            .isEqualTo(state)
        assertThat(LoadReducer.reduce(state, LoadResult.Failed(1, LoadError.Unavailable)))
            .isEqualTo(state)
    }

    @Test
    fun cancellationFinishesOnlyTheMatchingRequest() {
        val state = LoadUiState(items = listOf("old"), isLoading = true, requestId = 2)
        assertThat(LoadReducer.reduce(state, LoadResult.Cancelled(1))).isEqualTo(state)
        assertThat(LoadReducer.reduce(state, LoadResult.Cancelled(2)))
            .isEqualTo(LoadUiState(items = listOf("old")))
    }
}
