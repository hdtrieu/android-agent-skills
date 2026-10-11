# Kotlin test skeletons

Shapes to adapt, not to paste. Names, assertion library (Truth, AssertK, kotlin.test, JUnit) and
mocking style follow the repository. All examples assume JUnit4 + `kotlinx-coroutines-test`;
Turbine is used where noted.

## Test dispatcher rule

Use the repository's rule when it has one. Otherwise:

```kotlin
class MainDispatcherRule(
    val dispatcher: TestDispatcher = StandardTestDispatcher(),
) : TestWatcher() {
    override fun starting(description: Description) = Dispatchers.setMain(dispatcher)
    override fun finished(description: Description) = Dispatchers.resetMain()
}
```

Inject `mainDispatcherRule.dispatcher` (or a dispatcher built on the same scheduler) wherever
the production code takes a dispatcher qualifier, so `runTest` controls every coroutine.

## Pure reducer

```kotlin
class ProfileReducerTest {
    @Test
    fun `stale load result does not overwrite the newer request`() {
        val state = ProfileUiState(isLoading = true, loadRequestId = 2)
        val actual = ProfileReducer.reduce(state, ProfileResult.Loaded(requestId = 1, profile = profile("old")))
        assertEquals(state, actual)
    }

    @Test
    fun `failure keeps existing content for retry`() {
        val state = ProfileUiState(profile = profile("Alex"), isLoading = true, loadRequestId = 1)
        val actual = ProfileReducer.reduce(state, ProfileResult.LoadFailed(1, ProfileErrorUi.Offline))
        assertEquals(ProfileUiState(profile = profile("Alex"), error = ProfileErrorUi.Offline), actual)
    }
}
```

## ViewModel with a gated fake

```kotlin
class FakeProfileRepository : ProfileRepository {
    private val gates = ArrayDeque<CompletableDeferred<Profile>>()
    var saveCalls = 0
    fun nextLoad(): CompletableDeferred<Profile> = CompletableDeferred<Profile>().also(gates::addLast)
    override suspend fun profile(): Profile = gates.removeFirst().await()
    override suspend fun save(profile: Profile) { saveCalls++ }
}

class ProfileViewModelTest {
    @get:Rule val main = MainDispatcherRule()
    private val repository = FakeProfileRepository()
    private val viewModel by lazy { ProfileViewModel(GetProfileUseCase(repository), SaveProfileUseCase(repository)) }

    @Test
    fun `old load finishing after a new one cannot overwrite it`() = runTest {
        val first = repository.nextLoad()
        val second = repository.nextLoad()
        viewModel.onAction(ProfileAction.Load)
        viewModel.onAction(ProfileAction.Load)      // policy: cancels the first
        second.complete(profile("new"))
        first.complete(profile("old"))
        advanceUntilIdle()
        assertEquals("new", viewModel.uiState.value.profile?.name)
    }

    @Test
    fun `cancelling the previous load is not reported as an error`() = runTest {
        repository.nextLoad()                        // first load never completes; it gets cancelled
        val second = repository.nextLoad()
        viewModel.onAction(ProfileAction.Load)
        runCurrent()
        viewModel.onAction(ProfileAction.Load)
        second.complete(profile("new"))
        advanceUntilIdle()
        assertNull(viewModel.uiState.value.error)
        assertFalse(viewModel.uiState.value.isLoading)
    }

    @Test
    fun `duplicate save while saving is ignored`() = runTest {
        // arrange loaded state, then:
        viewModel.onAction(ProfileAction.Save)
        viewModel.onAction(ProfileAction.Save)
        advanceUntilIdle()
        assertEquals(1, repository.saveCalls)
    }
}
```

## Flows with Turbine

```kotlin
@Test
fun `emits loading then content`() = runTest {
    viewModel.uiState.test {
        assertEquals(ProfileUiState(), awaitItem())
        viewModel.onAction(ProfileAction.Load)
        assertTrue(awaitItem().isLoading)
        gate.complete(profile("Alex"))
        assertEquals("Alex", awaitItem().profile?.name)
        cancelAndIgnoreRemainingEvents()
    }
}
```

For `stateIn(WhileSubscribed)` without Turbine:

```kotlin
backgroundScope.launch(UnconfinedTestDispatcher(testScheduler)) { viewModel.uiState.collect() }
```

## Compose content (Robolectric or instrumented)

```kotlin
@RunWith(AndroidJUnit4::class)
class ProfileScreenTest {
    @get:Rule val compose = createComposeRule()

    @Test
    fun `error state shows retry and emits Retry`() {
        val actions = mutableListOf<ProfileAction>()
        compose.setContent {
            AppTheme { ProfileScreen(state = ProfileUiState(error = ProfileErrorUi.Offline), onAction = actions::add, onBack = {}) }
        }
        compose.onNodeWithText(getString(R.string.profile_retry)).assertIsDisplayed().performClick()
        assertEquals(listOf(ProfileAction.Retry), actions)
    }
}
```

Use resource lookups, not hard-coded copy, so locale changes do not break tests. Robolectric
Compose tests need `testOptions.unitTests.isIncludeAndroidResources = true`.

## A1 — input matrix through the real decoder

```kotlin
class ProfileDtoMappingTest {
    private val json = Json { ignoreUnknownKeys = true }
    private val captured = resource("profile/profile_response.json") // sanitized, source noted

    private data class Case(val label: String, val mutate: (JsonObject) -> JsonObject, val expected: Profile?)

    @Test
    fun `input matrix`() {
        listOf(
            Case("happy path", { it }, profile(name = "Alex", age = 30)),
            Case("name missing", { it.without("name") }, profile(name = "", age = 30)),
            Case("name null", { it.with("name", JsonNull) }, profile(name = "", age = 30)),
            Case("age 0 is valid", { it.with("age", JsonPrimitive(0)) }, profile(name = "Alex", age = 0)),
        ).forEach { case ->
            val dto = json.decodeFromJsonElement<ProfileDto>(case.mutate(captured))
            assertEquals(case.label, case.expected, dto.toDomain())
        }
    }

    @Test
    fun `unknown status is a typed error, not a default`() {
        val dto = json.decodeFromJsonElement<ProfileDto>(captured.with("status", JsonPrimitive("nope")))
        assertFailsWith<UnknownProfileStatus> { dto.toDomain() }
    }
}
```

## A2 — loop closure

```kotlin
@Test
fun `after handling a remote change once, the next check reports synced`() = runTest {
    remote.updatedAt = 200; local.updatedAt = 100
    assertEquals(SyncState.Changed, repository.check())
    repository.acceptRemote()
    assertEquals(SyncState.Synced, repository.check())   // the assertion that catches "fires forever"
}
```

## A3 — identity with a decoy

```kotlin
@Test
fun `selects by id, not by position`() {
    val decoy = item(id = "a", price = 11)
    val target = item(id = "b", price = 98)
    assertEquals(98, priceOf(listOf(decoy, target), id = "b"))   // first/last/sum all fail loudly
}
```

## A4 — forced interleaving

```kotlin
@Test
fun `logout while a load is pending discards the result`() = runTest {
    val gate = repository.nextLoad()
    viewModel.onAction(Load)
    session.logout()
    gate.complete(profile("previous user"))
    advanceUntilIdle()
    assertNull(viewModel.uiState.value.profile)
}
```

## A5 — transition table

```kotlin
@Test
fun `legal transitions`() = listOf(
    Status.Draft to Status.Submitted,
    Status.Submitted to Status.Approved,
).forEach { (from, to) -> assertEquals(to, transition(from, to)) }

@Test
fun `terminal states reject every writer`() {
    Status.entries.forEach { target ->
        if (target != Status.Cancelled) assertFailsWith<IllegalTransition> { transition(Status.Cancelled, target) }
    }
}
```

## A6 — two accounts

```kotlin
@Test
fun `account B cannot read account A codes`() = runTest {
    store.save(accountA, codes("A-1"))
    assertTrue(store.read(accountB).isEmpty())
    assertEquals(codes("A-1"), store.read(accountA))   // and A is untouched
}
```

## A9 — old data against new readers

```kotlin
@Test
fun `migration 3 to 4 keeps existing rows`() {
    helper.createDatabase(DB, 3).use { it.execSQL("INSERT INTO item (id, kind) VALUES ('1', 'LEGACY')") }
    val db = helper.runMigrationsAndValidate(DB, 4, true, MIGRATION_3_4)
    db.query("SELECT kind FROM item WHERE id = '1'").use { it.moveToFirst(); assertEquals("STANDARD", it.getString(0)) }
}
```

## A10 — bound and bound+1

```kotlin
@Test
fun `fetches every page past the server limit`() = runTest {
    remote.items = List(101) { item(id = "$it") }   // server page size 100
    assertEquals(101, repository.all().size)
}
```

## A11 — independent copies

```kotlin
@Test
fun `deleting a duplicate leaves the original file`() = runTest {
    val original = attachments.add(file("a.png"))
    val copy = attachments.duplicate(original)
    assertNotEquals(original.localId, copy.localId)
    attachments.delete(copy)
    assertTrue(files.exists(original.localId))
}
```

## A12 — deferred work and ownership change

```kotlin
@Test
fun `debounced save after switching item writes to the original item only`() = runTest {
    editor.open(itemA)
    editor.type("draft")
    editor.open(itemB)                  // ownership changes inside the debounce window
    advanceTimeBy(DEBOUNCE + 1)
    assertEquals("draft", store.text(itemA))
    assertEquals("", store.text(itemB))
}
```
